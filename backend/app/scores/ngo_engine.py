"""
NGO Transparency Score Engine.

Aggregates historical project verification performance across an NGO's entire portfolio.
Uses a configurable multi-factor weighted model considering:
1. Weighted Evidence Quality (financial-value-weighted average of project evidence scores)
2. Project Financial Value & Verification Status (% of project value supported by verified evidence)
3. Independent Audit History (confirmed vs rejected/discrepancy audits)
4. Disputes (active disputes and overall dispute rate)
5. Historical Performance & Trend (improving, stable, declining)

DO NOT describe the score as: "Probability that NGO is honest."
Describe it as: "Evidence-based transparency/verification indicator."

Persists historical ScoreSnapshots and emits ActivityLogs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.activity import ActivityLog
from app.models.audit import Audit, AuditDecision
from app.models.dispute import Dispute
from app.models.enums import (
    AuditDecisionType,
    DisputeStatus,
    HistoricalTrend,
    ProjectStatus,
)
from app.models.ngo import NGO
from app.models.project import Project
from app.models.score import ScoreSnapshot
from app.schemas.score import (
    NGOTransparencyFactor,
    NGOTransparencyScoreResponse,
)
from app.scores.engine import get_score_engine

logger = logging.getLogger(__name__)

OFFICIAL_INDICATOR_DESCRIPTION = "Evidence-based transparency/verification indicator."


@dataclass
class NGOTransparencyScoreWeights:
    """Configurable weights for the NGO Transparency Score Engine."""
    evidence_quality: float = field(
        default_factory=lambda: get_settings().NGO_SCORE_WEIGHT_EVIDENCE_QUALITY
    )
    value_verification: float = field(
        default_factory=lambda: get_settings().NGO_SCORE_WEIGHT_VALUE_VERIFICATION
    )
    audit_performance: float = field(
        default_factory=lambda: get_settings().NGO_SCORE_WEIGHT_AUDIT_PERFORMANCE
    )
    dispute_impact: float = field(
        default_factory=lambda: get_settings().NGO_SCORE_WEIGHT_DISPUTE_IMPACT
    )
    historical_trend: float = field(
        default_factory=lambda: get_settings().NGO_SCORE_WEIGHT_HISTORICAL_TREND
    )

    def normalized(self) -> "NGOTransparencyScoreWeights":
        total = (
            self.evidence_quality
            + self.value_verification
            + self.audit_performance
            + self.dispute_impact
            + self.historical_trend
        )
        if total <= 0:
            return NGOTransparencyScoreWeights(0.35, 0.25, 0.20, 0.10, 0.10)
        return NGOTransparencyScoreWeights(
            evidence_quality=self.evidence_quality / total,
            value_verification=self.value_verification / total,
            audit_performance=self.audit_performance / total,
            dispute_impact=self.dispute_impact / total,
            historical_trend=self.historical_trend / total,
        )


class NGOTransparencyScoreEngine:
    """
    Authoritative server-side NGO Transparency Score Engine.
    Computes an explainable, multi-factor transparency score and persists snapshots.
    """

    def __init__(self, weights: Optional[NGOTransparencyScoreWeights] = None):
        self.weights = (weights or NGOTransparencyScoreWeights()).normalized()

    async def calculate_score(
        self,
        db: AsyncSession,
        ngo: NGO,
        weights_override: Optional[NGOTransparencyScoreWeights] = None,
        record_snapshot: bool = True,
    ) -> NGOTransparencyScoreResponse:
        """
        Calculate the NGO Transparency Score, generate explainable narrative bullets,
        and optionally persist a historical ScoreSnapshot.
        """
        now = datetime.now(timezone.utc)
        active_weights = (weights_override or self.weights).normalized()

        # 1. Fetch all projects belonging to this NGO
        proj_stmt = (
            select(Project)
            .where(Project.ngo_id == ngo.id)
            .order_by(Project.created_at.asc())
        )
        proj_res = await db.execute(proj_stmt)
        projects: List[Project] = list(proj_res.scalars().all())

        project_count = len(projects)

        # Ensure project evidence scores are calculated
        score_engine = get_score_engine()
        for p in projects:
            if p.evidence_score is None:
                try:
                    await score_engine.calculate_score(db, p, record_snapshot=False)
                except Exception as e:
                    logger.warning("Could not pre-calculate score for project %s: %s", p.id, e)

        # 2. Categorize verification statuses
        verified_count = 0
        partially_verified_count = 0
        pending_count = 0
        disputed_count = 0

        for p in projects:
            if p.status == ProjectStatus.VERIFIED:
                verified_count += 1
            elif p.status == ProjectStatus.PARTIALLY_VERIFIED:
                partially_verified_count += 1
            elif p.status == ProjectStatus.DISPUTED:
                disputed_count += 1
            else:
                # CREATED, FUNDING, EVIDENCE_COLLECTION, UNDER_VERIFICATION, PENDING
                pending_count += 1

        # 3. Fetch audits and decisions for all projects of this NGO
        audits: List[Audit] = []
        if projects:
            proj_ids = [p.id for p in projects]
            audit_stmt = (
                select(Audit)
                .where(Audit.project_id.in_(proj_ids))
                .options(selectinload(Audit.decisions))
            )
            audit_res = await db.execute(audit_stmt)
            audits = list(audit_res.scalars().all())

        # 4. Fetch disputes across all projects of this NGO
        disputes: List[Dispute] = []
        if projects:
            proj_ids = [p.id for p in projects]
            disp_stmt = (
                select(Dispute)
                .where(Dispute.project_id.in_(proj_ids))
            )
            disp_res = await db.execute(disp_stmt)
            disputes = list(disp_res.scalars().all())

        # 5. Fetch prior NGO ScoreSnapshots (for historical trend)
        snap_stmt = (
            select(ScoreSnapshot)
            .where(
                ScoreSnapshot.ngo_id == ngo.id,
                ScoreSnapshot.project_id.is_(None),
            )
            .order_by(ScoreSnapshot.calculated_at.desc())
            .limit(10)
        )
        snap_res = await db.execute(snap_stmt)
        past_snapshots: List[ScoreSnapshot] = list(snap_res.scalars().all())

        # ── DIMENSION 1: Weighted Evidence Quality ──────────────────────
        dim1_score, dim1_expl, dim1_bullet, dim1_details = self._calculate_evidence_quality(projects)

        # ── DIMENSION 2: Value-Weighted Verification ────────────────────
        dim2_score, dim2_expl, dim2_bullet, dim2_details = self._calculate_value_verification(projects)

        # ── DIMENSION 3: Independent Audit Performance ──────────────────
        dim3_score, dim3_expl, dim3_bullet, dim3_details = self._calculate_audit_performance(audits)

        # ── DIMENSION 4: Dispute Impact ─────────────────────────────────
        dim4_score, dim4_expl, dim4_bullet, dim4_details = self._calculate_dispute_impact(
            projects, disputes, disputed_count
        )

        # ── DIMENSION 5: Historical Performance & Trend ─────────────────
        dim5_score, dim5_trend, dim5_expl, dim5_bullet, dim5_details = self._calculate_historical_trend(
            projects, past_snapshots
        )

        # ── FACTORS BUILDER ─────────────────────────────────────────────
        factors: Dict[str, NGOTransparencyFactor] = {
            "evidence_quality": NGOTransparencyFactor(
                factor_name="Weighted Evidence Quality",
                weight=round(active_weights.evidence_quality, 4),
                raw_score=round(dim1_score, 1),
                weighted_score=round(dim1_score * active_weights.evidence_quality, 2),
                explanation=dim1_expl,
                details=dim1_details,
            ),
            "value_verification": NGOTransparencyFactor(
                factor_name="Value-Weighted Verification",
                weight=round(active_weights.value_verification, 4),
                raw_score=round(dim2_score, 1),
                weighted_score=round(dim2_score * active_weights.value_verification, 2),
                explanation=dim2_expl,
                details=dim2_details,
            ),
            "audit_performance": NGOTransparencyFactor(
                factor_name="Independent Audit Performance",
                weight=round(active_weights.audit_performance, 4),
                raw_score=round(dim3_score, 1),
                weighted_score=round(dim3_score * active_weights.audit_performance, 2),
                explanation=dim3_expl,
                details=dim3_details,
            ),
            "dispute_impact": NGOTransparencyFactor(
                factor_name="Dispute Impact",
                weight=round(active_weights.dispute_impact, 4),
                raw_score=round(dim4_score, 1),
                weighted_score=round(dim4_score * active_weights.dispute_impact, 2),
                explanation=dim4_expl,
                details=dim4_details,
            ),
            "historical_trend": NGOTransparencyFactor(
                factor_name="Historical Performance Trend",
                weight=round(active_weights.historical_trend, 4),
                raw_score=round(dim5_score, 1),
                weighted_score=round(dim5_score * active_weights.historical_trend, 2),
                explanation=dim5_expl,
                details=dim5_details,
            ),
        }

        # ── COMPOSITE SCORE ─────────────────────────────────────────────
        raw_final = sum(f.weighted_score for f in factors.values())
        final_score = round(max(0.0, min(100.0, raw_final)), 1)

        # ── EXPLANATION BULLETS ──────────────────────────────────────────
        explanation_bullets: List[str] = [
            dim1_bullet,
            dim2_bullet,
            dim4_bullet,
            dim3_bullet,
        ]
        if dim5_bullet:
            explanation_bullets.append(dim5_bullet)

        # ── PERSIST SCORE SNAPSHOT ──────────────────────────────────────
        snapshot_id: Optional[uuid.UUID] = None
        if record_snapshot:
            snapshot_data = {
                "final_score": final_score,
                "project_count": project_count,
                "verified_count": verified_count,
                "partially_verified_count": partially_verified_count,
                "pending_count": pending_count,
                "disputed_count": disputed_count,
                "weighted_evidence_quality": round(dim1_score, 1),
                "audit_performance": round(dim3_score, 1),
                "historical_trend": dim5_trend.value,
                "explanation": explanation_bullets,
                "weights": {
                    "evidence_quality": active_weights.evidence_quality,
                    "value_verification": active_weights.value_verification,
                    "audit_performance": active_weights.audit_performance,
                    "dispute_impact": active_weights.dispute_impact,
                    "historical_trend": active_weights.historical_trend,
                },
                "factors": {
                    k: {
                        "factor_name": v.factor_name,
                        "weight": v.weight,
                        "raw_score": v.raw_score,
                        "weighted_score": v.weighted_score,
                        "explanation": v.explanation,
                        "details": v.details,
                    }
                    for k, v in factors.items()
                },
            }

            snapshot = ScoreSnapshot(
                ngo_id=ngo.id,
                project_id=None,
                composite_score=final_score,
                breakdown=snapshot_data,
                calculated_at=now,
            )
            db.add(snapshot)

            # Record ActivityLog
            activity = ActivityLog(
                action="NGO_SCORE_CALCULATED",
                actor_id=None,
                actor_role="SYSTEM",
                resource_type="NGO",
                resource_id=str(ngo.id),
                detail={
                    "ngo_id": str(ngo.id),
                    "ngo_name": ngo.name,
                    "final_score": final_score,
                    "project_count": project_count,
                    "historical_trend": dim5_trend.value,
                },
            )
            db.add(activity)
            await db.flush()
            snapshot_id = snapshot.id

        return NGOTransparencyScoreResponse(
            ngo_id=ngo.id,
            ngo_name=ngo.name,
            final_score=final_score,
            indicator_description=OFFICIAL_INDICATOR_DESCRIPTION,
            project_count=project_count,
            verified_count=verified_count,
            partially_verified_count=partially_verified_count,
            pending_count=pending_count,
            disputed_count=disputed_count,
            weighted_evidence_quality=round(dim1_score, 1),
            audit_performance=round(dim3_score, 1),
            historical_trend=dim5_trend.value,
            explanation=explanation_bullets,
            factors=factors,
            calculated_at=now,
            snapshot_id=snapshot_id,
        )

    # ── PRIVATE DIMENSION CALCULATIONS ──────────────────────────────────

    def _calculate_evidence_quality(
        self, projects: List[Project]
    ) -> tuple[float, str, str, Dict[str, Any]]:
        """
        Dimension 1: Financial-value-weighted average of project evidence scores.
        """
        if not projects:
            return (
                50.0,
                "No projects submitted yet; baseline pending initial evidence.",
                "Baseline evidence pending initial project submissions",
                {"scored_projects": 0, "total_value_weighted": 0.0},
            )

        total_weight = 0.0
        weighted_sum = 0.0

        for p in projects:
            score = float(p.evidence_score or 50.0)
            # Use financial value as weight; if 0 or missing, apply nominal baseline weight of 1000.0
            weight = max(float(p.target_amount or 0.0), 1000.0)
            weighted_sum += score * weight
            total_weight += weight

        raw_score = min(100.0, max(0.0, weighted_sum / total_weight)) if total_weight > 0 else 50.0

        if raw_score >= 80.0:
            expl = "Strong evidence quality demonstrated across recent and high-value projects."
            bullet = "Strong evidence across recent projects"
        elif raw_score >= 60.0:
            expl = "Moderate evidence quality documented across submitted project milestones."
            bullet = "Moderate evidence across submitted projects"
        elif raw_score >= 40.0:
            expl = "Limited evidence documented; several project verification signals incomplete."
            bullet = "Limited evidence across project portfolio"
        else:
            expl = "Weak evidence recorded across projects; critical verifications missing."
            bullet = "Weak evidence quality across project portfolio"

        details = {
            "scored_projects_count": len(projects),
            "value_weighted_score": round(raw_score, 2),
        }
        return raw_score, expl, bullet, details

    def _calculate_value_verification(
        self, projects: List[Project]
    ) -> tuple[float, str, str, Dict[str, Any]]:
        """
        Dimension 2: Project Financial Value & Verification Status.
        Calculates percentage of total project financial value supported by verified evidence.
        """
        if not projects:
            return (
                50.0,
                "No project expenditure allocated yet; neutral baseline applied.",
                "No project financial value allocated yet",
                {"total_value": 0.0, "verified_value_pct": 0.0},
            )

        total_value = sum(float(p.target_amount or 0.0) for p in projects)
        has_monetary_value = total_value > 0

        verified_val = 0.0
        partial_val = 0.0
        pending_val = 0.0
        disputed_val = 0.0

        for p in projects:
            val = float(p.target_amount or 0.0) if has_monetary_value else 1.0
            if p.status == ProjectStatus.VERIFIED:
                verified_val += val
            elif p.status == ProjectStatus.PARTIALLY_VERIFIED:
                partial_val += val
            elif p.status == ProjectStatus.DISPUTED:
                disputed_val += val
            else:
                pending_val += val

        divisor = total_value if has_monetary_value else float(len(projects))
        # Supported value considers 100% of fully verified value + 70% of partially verified value
        effective_supported = verified_val + (partial_val * 0.70)
        percentage_supported = round((effective_supported / divisor) * 100, 1)

        # Baseline value score incorporates pending with modest credit (30%), zero for disputed
        raw_score = min(
            100.0,
            max(
                0.0,
                ((verified_val * 1.0 + partial_val * 0.70 + pending_val * 0.30) / divisor) * 100,
            ),
        )

        bullet_pct = int(round(percentage_supported))
        bullet = f"{bullet_pct}% of project value supported by verified evidence"
        expl = (
            f"{bullet_pct}% of total project financial value supported by verified or partially "
            f"verified evidence across {len(projects)} projects."
        )

        details = {
            "total_portfolio_value": total_value,
            "verified_value": verified_val,
            "partially_verified_value": partial_val,
            "pending_value": pending_val,
            "disputed_value": disputed_val,
            "supported_percentage": percentage_supported,
        }
        return raw_score, expl, bullet, details

    def _calculate_audit_performance(
        self, audits: List[Audit]
    ) -> tuple[float, str, str, Dict[str, Any]]:
        """
        Dimension 3: Independent Audit History.
        """
        if not audits:
            return (
                75.0,
                "No independent audits conducted yet; clean baseline standing.",
                "Positive independent audit history",
                {"audits_count": 0, "decisions_count": 0},
            )

        audit_scores: List[float] = []
        confirmed_count = 0
        partially_confirmed_count = 0
        discrepancy_count = 0
        rejected_count = 0

        for a in audits:
            # Sort decisions chronologically and take latest
            sorted_decisions = sorted(a.decisions, key=lambda d: d.decided_at)
            if not sorted_decisions:
                # Audit initiated but no decision yet
                audit_scores.append(70.0)
                continue

            latest = sorted_decisions[-1]
            if latest.decision in (
                AuditDecisionType.CONFIRMED,
                AuditDecisionType.APPROVED,
            ):
                audit_scores.append(100.0)
                confirmed_count += 1
            elif latest.decision in (
                AuditDecisionType.PARTIALLY_CONFIRMED,
                AuditDecisionType.APPROVED_WITH_CONDITIONS,
            ):
                audit_scores.append(70.0)
                partially_confirmed_count += 1
            elif latest.decision in (
                AuditDecisionType.DISCREPANCY,
                AuditDecisionType.FLAGGED_FRAUD,
            ):
                audit_scores.append(25.0)
                discrepancy_count += 1
            elif latest.decision == AuditDecisionType.REJECTED:
                audit_scores.append(0.0)
                rejected_count += 1
            else:
                audit_scores.append(60.0)

        raw_score = sum(audit_scores) / len(audit_scores)

        if raw_score >= 80.0:
            expl = "Strong, positive independent audit findings across evaluated projects."
            bullet = "Positive independent audit history"
        elif raw_score >= 60.0:
            expl = "Generally satisfactory audit findings with minor conditions noted."
            bullet = "Satisfactory independent audit history"
        elif raw_score >= 40.0:
            expl = "Mixed independent audit findings with identified discrepancies."
            bullet = "Independent audit findings with conditional discrepancies"
        else:
            expl = "Significant discrepancies or rejections recorded during independent audits."
            bullet = "Unfavorable independent audit history"

        details = {
            "audits_count": len(audits),
            "confirmed_count": confirmed_count,
            "partially_confirmed_count": partially_confirmed_count,
            "discrepancy_count": discrepancy_count,
            "rejected_count": rejected_count,
        }
        return raw_score, expl, bullet, details

    def _calculate_dispute_impact(
        self,
        projects: List[Project],
        disputes: List[Dispute],
        disputed_projects_count: int,
    ) -> tuple[float, str, str, Dict[str, Any]]:
        """
        Dimension 4: Disputes.
        """
        active_disputes = sum(
            1 for d in disputes if d.status in (DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW)
        )
        resolved_disputes = sum(
            1 for d in disputes if d.status == DisputeStatus.RESOLVED
        )
        dismissed_disputes = sum(
            1 for d in disputes if d.status == DisputeStatus.DISMISSED
        )

        base_score = 100.0
        # Active disputes trigger a significant penalty
        penalty = active_disputes * 30.0
        # Past dismissed disputes carry a minor residual check
        penalty += dismissed_disputes * 10.0
        # Resolved disputes carry minimal penalty
        penalty += resolved_disputes * 5.0

        # Disputed project status penalty
        if projects and disputed_projects_count > 0:
            penalty += (disputed_projects_count / len(projects)) * 30.0

        raw_score = max(0.0, min(100.0, base_score - penalty))

        if len(disputes) == 0 and disputed_projects_count == 0:
            bullet = "Low dispute rate"
            expl = "Zero active or historical project disputes recorded."
        elif active_disputes > 0 or disputed_projects_count > 0:
            bullet = f"Active disputes under administrative review ({active_disputes} active)"
            expl = (
                f"{active_disputes} active project dispute(s) under review; "
                f"{disputed_projects_count} project(s) marked disputed."
            )
        else:
            bullet = "Low dispute rate"
            expl = f"All past disputes ({len(disputes)}) have been concluded and resolved."

        details = {
            "total_disputes": len(disputes),
            "active_disputes": active_disputes,
            "resolved_disputes": resolved_disputes,
            "dismissed_disputes": dismissed_disputes,
            "disputed_projects_count": disputed_projects_count,
        }
        return raw_score, expl, bullet, details

    def _calculate_historical_trend(
        self,
        projects: List[Project],
        past_snapshots: List[ScoreSnapshot],
    ) -> tuple[float, HistoricalTrend, str, Optional[str], Dict[str, Any]]:
        """
        Dimension 5: Historical Performance and Trend.
        Analyzes trajectory from past score snapshots and chronological project scores.
        """
        # 1. Compare snapshots if we have at least 2 historical snapshots
        if len(past_snapshots) >= 2:
            latest = float(past_snapshots[0].composite_score)
            previous = float(past_snapshots[1].composite_score)
            diff = latest - previous

            if diff >= 2.0:
                trend = HistoricalTrend.IMPROVING
                score = 95.0
                expl = f"Upward trajectory: +{round(diff, 1)} pts compared to previous assessment."
                bullet = "Improving historical verification performance"
            elif diff <= -2.0:
                trend = HistoricalTrend.DECLINING
                score = 45.0
                expl = f"Downward trajectory: {round(diff, 1)} pts compared to previous assessment."
                bullet = "Declining historical verification performance"
            else:
                trend = HistoricalTrend.STABLE
                score = 80.0
                expl = "Consistent historical performance across assessments."
                bullet = "Consistent verification performance over time"

            details = {
                "source": "score_snapshots",
                "latest_snapshot_score": latest,
                "previous_snapshot_score": previous,
                "diff": round(diff, 1),
            }
            return score, trend, expl, bullet, details

        # 2. If fewer than 2 snapshots, analyze chronological projects
        if len(projects) >= 3:
            mid = len(projects) // 2
            early_scores = [float(p.evidence_score or 50.0) for p in projects[:mid]]
            recent_scores = [float(p.evidence_score or 50.0) for p in projects[mid:]]
            avg_early = sum(early_scores) / len(early_scores)
            avg_recent = sum(recent_scores) / len(recent_scores)
            diff = avg_recent - avg_early

            if diff >= 3.0:
                trend = HistoricalTrend.IMPROVING
                score = 90.0
                expl = f"Evidence quality improving across recent projects (+{round(diff, 1)} pts)."
                bullet = "Improving historical verification performance"
            elif diff <= -3.0:
                trend = HistoricalTrend.DECLINING
                score = 50.0
                expl = f"Evidence quality declining across recent projects ({round(diff, 1)} pts)."
                bullet = "Declining historical verification performance"
            else:
                trend = HistoricalTrend.STABLE
                score = 75.0
                expl = "Evidence quality stable across project portfolio."
                bullet = "Consistent verification performance over time"

            details = {
                "source": "project_evidence_scores",
                "avg_early": round(avg_early, 1),
                "avg_recent": round(avg_recent, 1),
                "diff": round(diff, 1),
            }
            return score, trend, expl, bullet, details

        # 3. Insufficient data
        trend = HistoricalTrend.INSUFFICIENT_DATA
        score = 70.0
        expl = "Insufficient project history to establish long-term trajectory."
        details = {
            "source": "insufficient_data",
            "project_count": len(projects),
            "snapshot_count": len(past_snapshots),
        }
        return score, trend, expl, None, details


# Singleton instance
_ngo_engine_instance: Optional[NGOTransparencyScoreEngine] = None


def get_ngo_score_engine() -> NGOTransparencyScoreEngine:
    global _ngo_engine_instance
    if _ngo_engine_instance is None:
        _ngo_engine_instance = NGOTransparencyScoreEngine()
    return _ngo_engine_instance
