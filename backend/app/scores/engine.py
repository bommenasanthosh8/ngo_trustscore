"""
Project Evidence Score Engine.

Calculates the authoritative 100-point project evidence score across 6 core dimensions:
1. Location consistency       = 20 pts max
2. Timeline / timestamp       = 15 pts max
3. Media evidence             = 20 pts max
4. Financial evidence         = 20 pts max
5. Project identity / details = 10 pts max
6. Independent audit          = 15 pts max
-----------------------------------------
TOTAL                         = 100 pts

Produces factor breakdown with earned points, max points, narrative explanations,
and source verification references.
Persists ScoreSnapshot and updates project.evidence_score.
Reflects active dispute statuses clearly.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.activity import ActivityLog
from app.models.audit import Audit, AuditDecision
from app.models.dispute import Dispute
from app.models.enums import (
    AuditDecisionType,
    DisputeStatus,
    EvidenceType,
    FinancialConsistencyStatus,
    NGOVerificationStatus,
    ProjectStatus,
    ScoreStatus,
    VerificationModel,
    VerificationStatus,
)
from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence
from app.models.project import Project
from app.models.score import ScoreSnapshot
from app.schemas.score import ProjectScoreResponse, ScoreFactorResult
from app.schemas.verification import CheckResultSchema, VerificationReportResponse
from app.verification.engine import VerificationEngine

logger = logging.getLogger(__name__)


class ProjectScoreEngine:
    """
    Authoritative server-side scoring engine.
    Calculates 100-point composite evidence score and persists snapshots.
    """

    def __init__(self, verification_engine: Optional[VerificationEngine] = None):
        self.verification_engine = verification_engine or VerificationEngine()

    async def calculate_score(
        self,
        db: AsyncSession,
        project: Project,
        record_snapshot: bool = True,
    ) -> ProjectScoreResponse:
        """
        Calculate the 100-point evidence score for a project, update project record,
        and optionally persist a ScoreSnapshot.
        """
        now = datetime.now(timezone.utc)

        # 1. Fetch project evidence items
        ev_stmt = (
            select(Evidence)
            .where(Evidence.project_id == project.id)
            .order_by(Evidence.uploaded_at.asc())
        )
        ev_res = await db.execute(ev_stmt)
        evidences: List[Evidence] = list(ev_res.scalars().all())

        # 2. Fetch project financial evidence items
        fin_stmt = (
            select(FinancialEvidence)
            .where(FinancialEvidence.project_id == project.id)
            .order_by(FinancialEvidence.uploaded_at.asc())
        )
        fin_res = await db.execute(fin_stmt)
        financials: List[FinancialEvidence] = list(fin_res.scalars().all())

        # 3. Fetch audits and decisions
        audit_stmt = (
            select(Audit)
            .where(Audit.project_id == project.id)
            .options(selectinload(Audit.decisions))
            .order_by(Audit.created_at.desc())
        )
        audit_res = await db.execute(audit_stmt)
        audits: List[Audit] = list(audit_res.scalars().all())

        # 4. Fetch disputes
        disp_stmt = (
            select(Dispute)
            .where(Dispute.project_id == project.id)
            .order_by(Dispute.created_at.desc())
        )
        disp_res = await db.execute(disp_stmt)
        disputes: List[Dispute] = list(disp_res.scalars().all())

        # Preserve project status (score calculation must not mutate project status)
        saved_status = project.status

        # 5. Run verification suite to get underlying check results
        ver_report = await self.verification_engine.verify_project(db, project)
        project.status = saved_status

        checks_map: Dict[str, CheckResultSchema] = {
            c.check_name: c for c in ver_report.individual_checks
        }

        # 6. Evaluate each of the 6 dimensions
        factor_location = self._evaluate_location(project, checks_map.get("LocationCheck"), evidences)
        factor_timeline = self._evaluate_timeline(project, checks_map.get("TimelineCheck"), checks_map.get("TimestampCheck"), evidences)
        factor_media = self._evaluate_media(project, checks_map, evidences)
        factor_financial = self._evaluate_financial(project, checks_map.get("FinancialConsistencyCheck"), checks_map.get("OCRCheck"), financials)
        factor_identity = await self._evaluate_identity(db, project, checks_map.get("ProjectIdentityCheck"))
        factor_audit = self._evaluate_audit(project, audits, disputes)

        factors = {
            "location_consistency": factor_location,
            "timeline_timestamp": factor_timeline,
            "media_evidence": factor_media,
            "financial_evidence": factor_financial,
            "project_identity": factor_identity,
            "independent_audit": factor_audit,
        }

        # 7. Compute total earned points (clamped 0 to 100)
        total_points = sum(f.earned_points for f in factors.values())
        final_score = round(max(0.0, min(100.0, total_points)), 1)

        # 8. Determine Score Status
        if final_score >= 80.0:
            status = ScoreStatus.STRONG_EVIDENCE
        elif final_score >= 65.0:
            status = ScoreStatus.GOOD_EVIDENCE
        elif final_score >= 45.0:
            status = ScoreStatus.LIMITED_EVIDENCE
        else:
            status = ScoreStatus.WEAK_EVIDENCE

        # 9. Dispute detection
        active_dispute = next(
            (d for d in disputes if d.status in [DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW]),
            None,
        )
        is_disputed = (project.status == ProjectStatus.DISPUTED) or (active_dispute is not None)
        dispute_status_val = active_dispute.status if active_dispute else (
            DisputeStatus.OPEN if project.status == ProjectStatus.DISPUTED else None
        )

        # 10. Overall summary explanation
        summary_parts = []
        if is_disputed:
            summary_parts.append(
                f"[DISPUTED] Project is under formal dispute ({dispute_status_val.value if dispute_status_val else 'ACTIVE'})."
            )

        summary_parts.append(
            f"Evidence Score: {final_score}/100 ({status.value.replace('_', ' ')})."
        )

        strengths = []
        concerns = []
        for fname, f in factors.items():
            if f.percentage >= 80.0:
                strengths.append(f"{f.factor_name} ({f.earned_points:.0f}/{f.maximum_points:.0f})")
            elif f.percentage < 50.0:
                concerns.append(f"{f.factor_name} ({f.earned_points:.0f}/{f.maximum_points:.0f})")

        if strengths:
            summary_parts.append(f"Strong areas: {', '.join(strengths)}.")
        if concerns:
            summary_parts.append(f"Areas needing attention: {', '.join(concerns)}.")

        overall_explanation = " ".join(summary_parts)

        # 11. Persist ScoreSnapshot and update Project
        if record_snapshot:
            snapshot_data = {
                "final_score": final_score,
                "status": status.value,
                "is_disputed": is_disputed,
                "dispute_status": dispute_status_val.value if dispute_status_val else None,
                "factors": {
                    k: {
                        "earned_points": v.earned_points,
                        "maximum_points": v.maximum_points,
                        "percentage": v.percentage,
                        "explanation": v.explanation,
                        "source_verification_results": v.source_verification_results,
                    }
                    for k, v in factors.items()
                },
                "explanation": overall_explanation,
            }

            snapshot = ScoreSnapshot(
                project_id=project.id,
                ngo_id=project.ngo_id,
                composite_score=final_score,
                breakdown=snapshot_data,
                calculated_at=now,
            )
            db.add(snapshot)

            project.evidence_score = final_score
            project.evidence_score_updated_at = now

            # Record ActivityLog
            activity = ActivityLog(
                action="SCORE_CALCULATED",
                actor_id=project.created_by_id,
                actor_role="SYSTEM",
                resource_type="Project",
                resource_id=str(project.id),
                detail={
                    "project_code": project.project_code,
                    "final_score": final_score,
                    "status": status.value,
                    "is_disputed": is_disputed,
                },
            )
            db.add(activity)
            await db.flush()

        return ProjectScoreResponse(
            project_id=project.id,
            project_code=project.project_code,
            project_title=project.title,
            final_score=final_score,
            status=status,
            is_disputed=is_disputed,
            dispute_status=dispute_status_val,
            explanation=overall_explanation,
            factors=factors,
            calculated_at=now,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # FACTOR 1: Location Consistency (Max 20 pts)
    # ──────────────────────────────────────────────────────────────────────────
    def _evaluate_location(
        self,
        project: Project,
        loc_check: Optional[CheckResultSchema],
        evidences: List[Evidence],
    ) -> ScoreFactorResult:
        max_pts = 20.0

        if not evidences:
            return ScoreFactorResult(
                factor_name="Location consistency",
                earned_points=0.0,
                maximum_points=max_pts,
                percentage=0.0,
                explanation="No physical evidence submitted for location verification.",
                source_verification_results={"status": "NO_EVIDENCE", "evidences_count": 0},
            )

        geo_evidences = [e for e in evidences if e.latitude is not None and e.longitude is not None]
        if not geo_evidences:
            return ScoreFactorResult(
                factor_name="Location consistency",
                earned_points=5.0,
                maximum_points=max_pts,
                percentage=25.0,
                explanation="Submitted evidence lacks GPS coordinates; location consistency could not be mathematically confirmed.",
                source_verification_results={"status": "UNAVAILABLE", "geo_evidences_count": 0},
            )

        if not loc_check:
            return ScoreFactorResult(
                factor_name="Location consistency",
                earned_points=10.0,
                maximum_points=max_pts,
                percentage=50.0,
                explanation="Location check data unavailable; neutral baseline applied.",
                source_verification_results={"status": "UNAVAILABLE"},
            )

        details = loc_check.details or {}
        dist = details.get("distance_meters")
        radius = float(project.geofence_radius or 500.0)
        status_val = loc_check.status.upper() if loc_check.status else "UNAVAILABLE"

        if status_val in ["MATCH", "PASSED", "VERIFIED"]:
            # Distance within geofence radius
            if dist is not None and dist <= 50.0:
                earned = 20.0
                expl = f"Evidence captured within {dist:.0f}m of project location."
            elif dist is not None and dist <= radius:
                # Scaled between 17 and 19
                fraction = dist / radius
                earned = round(20.0 - (fraction * 3.0), 1)
                expl = f"Evidence captured within {dist:.0f}m of project location (inside {radius:.0f}m geofence)."
            else:
                earned = 18.0
                expl = f"Evidence captured within project geofence ({radius:.0f}m radius)."
        elif status_val in ["NEAR", "WARNING", "FLAGGED"]:
            # NEAR: slightly outside geofence
            earned = 11.0
            dist_str = f"{dist:.0f}m" if dist is not None else "borderline"
            expl = f"Evidence captured near project location ({dist_str}), slightly exceeding {radius:.0f}m geofence."
        elif status_val in ["MISMATCH", "FAILED", "REJECTED"]:
            # MISMATCH: far outside geofence
            earned = 3.0
            dist_str = f"{(dist/1000.0):.1f}km" if (dist and dist >= 1000) else (f"{dist:.0f}m" if dist else "remote")
            expl = f"Location discrepancy: evidence captured {dist_str} from registered project site."
        else:
            earned = 6.0
            expl = "GPS coordinates unavailable on most submitted evidence items."

        return ScoreFactorResult(
            factor_name="Location consistency",
            earned_points=earned,
            maximum_points=max_pts,
            percentage=round((earned / max_pts) * 100, 1),
            explanation=expl,
            source_verification_results=details,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # FACTOR 2: Timeline / Timestamp (Max 15 pts)
    # ──────────────────────────────────────────────────────────────────────────
    def _evaluate_timeline(
        self,
        project: Project,
        timeline_check: Optional[CheckResultSchema],
        timestamp_check: Optional[CheckResultSchema],
        evidences: List[Evidence],
    ) -> ScoreFactorResult:
        max_pts = 15.0

        if not evidences:
            return ScoreFactorResult(
                factor_name="Timeline/timestamp",
                earned_points=0.0,
                maximum_points=max_pts,
                percentage=0.0,
                explanation="No evidence submitted across project lifecycle milestones.",
                source_verification_results={"status": "NO_EVIDENCE"},
            )

        types_present = {e.evidence_type for e in evidences}

        if project.verification_model == VerificationModel.PERMANENT:
            has_before = EvidenceType.BEFORE in types_present
            has_progress = EvidenceType.PROGRESS in types_present
            has_completion = EvidenceType.COMPLETION in types_present

            stages_count = sum([has_before, has_progress, has_completion])
            if stages_count == 3:
                base_pts = 15.0
                expl = "Before, progress and completion evidence available."
            elif stages_count == 2:
                base_pts = 10.0
                missing = [s for s, h in [("before", has_before), ("progress", has_progress), ("completion", has_completion)] if not h]
                expl = f"Partial lifecycle evidence: missing {', '.join(missing)} stage."
            else:
                base_pts = 5.0
                expl = "Limited milestone coverage: only single lifecycle stage submitted."
        elif project.verification_model == VerificationModel.ONE_TIME_EVENT:
            if EvidenceType.EVENT in types_present:
                base_pts = 15.0
                expl = "Event execution telemetry and confirmation evidence available."
            else:
                base_pts = 6.0
                expl = "One-time project missing dedicated EVENT milestone evidence."
        else:
            base_pts = 12.0
            expl = "Milestone evidence submitted."

        # Check timestamp check deductions
        deduction = 0.0
        if timestamp_check:
            ts_flags = timestamp_check.risk_flags or []
            if "EVIDENCE_PREDATES_PROJECT_START" in ts_flags or "EVIDENCE_AFTER_COMPLETION" in ts_flags:
                deduction += 3.0
            elif "COMPRESSED_TIMELINE" in ts_flags:
                deduction += 1.0
            elif timestamp_check.status in ["FAILED", "REJECTED"]:
                deduction += 3.0

        earned = round(max(0.0, min(max_pts, base_pts - deduction)), 1)
        source_data = {
            "stages_present": [t.value for t in types_present],
            "timeline_check": timeline_check.model_dump() if timeline_check else None,
            "timestamp_check": timestamp_check.model_dump() if timestamp_check else None,
        }

        return ScoreFactorResult(
            factor_name="Timeline/timestamp",
            earned_points=earned,
            maximum_points=max_pts,
            percentage=round((earned / max_pts) * 100, 1),
            explanation=expl,
            source_verification_results=source_data,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # FACTOR 3: Media Evidence (Max 20 pts)
    # ──────────────────────────────────────────────────────────────────────────
    def _evaluate_media(
        self,
        project: Project,
        checks_map: Dict[str, CheckResultSchema],
        evidences: List[Evidence],
    ) -> ScoreFactorResult:
        max_pts = 20.0

        if not evidences:
            return ScoreFactorResult(
                factor_name="Media evidence",
                earned_points=0.0,
                maximum_points=max_pts,
                percentage=0.0,
                explanation="No visual media files registered.",
                source_verification_results={"status": "NO_MEDIA"},
            )

        dup_check = checks_map.get("DuplicateMediaCheck")
        sim_check = checks_map.get("ImageSimilarityCheck")
        meta_check = checks_map.get("MetadataCheck")

        score = 20.0
        explanations = []

        # Duplicate check evaluation
        if dup_check and dup_check.risk_flags:
            if "CROSS_PROJECT_MEDIA_REUSE" in dup_check.risk_flags:
                score -= 10.0
                explanations.append("Identical media reused from another project")
            if "INTERNAL_EXACT_DUPLICATE" in dup_check.risk_flags:
                score -= 4.0
                explanations.append("Internal duplicate files detected")

        # Similarity check evaluation
        if sim_check and sim_check.risk_flags:
            if "BEFORE_COMPLETION_IDENTICAL_PHOTO" in sim_check.risk_flags:
                score -= 7.0
                explanations.append("Identical photo used for both before and completion milestones")
            elif sim_check.status and sim_check.status.upper() in ["FLAGGED", "WARNING"]:
                score -= 3.0

        # Metadata check evaluation
        if meta_check and meta_check.risk_flags:
            if "SUSPICIOUS_SOFTWARE" in meta_check.risk_flags:
                score -= 4.0
                explanations.append("External photo-editing software detected in EXIF")

        earned = round(max(0.0, min(max_pts, score)), 1)
        if not explanations:
            expl = "No exact duplicate detected; visual evidence is consistent."
        else:
            expl = f"Media anomalies detected: {'; '.join(explanations)}."

        return ScoreFactorResult(
            factor_name="Media evidence",
            earned_points=earned,
            maximum_points=max_pts,
            percentage=round((earned / max_pts) * 100, 1),
            explanation=expl,
            source_verification_results={
                "duplicate_media": dup_check.model_dump() if dup_check else None,
                "image_similarity": sim_check.model_dump() if sim_check else None,
                "metadata": meta_check.model_dump() if meta_check else None,
            },
        )

    # ──────────────────────────────────────────────────────────────────────────
    # FACTOR 4: Financial Evidence (Max 20 pts)
    # ──────────────────────────────────────────────────────────────────────────
    def _evaluate_financial(
        self,
        project: Project,
        fin_check: Optional[CheckResultSchema],
        ocr_check: Optional[CheckResultSchema],
        financials: List[FinancialEvidence],
    ) -> ScoreFactorResult:
        max_pts = 20.0

        if not financials:
            return ScoreFactorResult(
                factor_name="Financial evidence",
                earned_points=0.0,
                maximum_points=max_pts,
                percentage=0.0,
                explanation="No financial invoices or expenditure receipts submitted.",
                source_verification_results={"status": "NO_FINANCIALS"},
            )

        status_str = fin_check.status.upper() if fin_check and fin_check.status else ""
        details = fin_check.details if fin_check else {}
        claimed = float(details.get("claimed_total") or 0.0)
        supported = float(details.get("supported_total") or 0.0)
        cov_pct = (supported / claimed * 100.0) if claimed > 0 else (100.0 if supported > 0 else 0.0)

        if status_str == FinancialConsistencyStatus.CONSISTENT.value or cov_pct >= 95.0:
            earned = 19.0 if cov_pct >= 98.0 else 18.0
            expl = "Documents fully support claimed expenditure."
        elif status_str == FinancialConsistencyStatus.MINOR_DISCREPANCY.value or cov_pct >= 80.0:
            earned = 16.0
            expl = "Documents support most claimed expenditure."
        elif status_str == FinancialConsistencyStatus.MAJOR_DISCREPANCY.value or cov_pct > 0.0:
            earned = 7.0
            expl = f"Documented expenditure accounts for only {cov_pct:.0f}% of claimed expenditure."
        else:
            earned = 4.0
            expl = "Financial documents could not substantiate claimed expenditure."

        # Deductions for OCR or duplicate financial documents
        if ocr_check and ocr_check.risk_flags:
            if "OCR_AMOUNT_MISMATCH" in ocr_check.risk_flags:
                earned = max(2.0, earned - 3.0)
                expl += " (OCR detected invoice amount mismatch)"
            if "OCR_FOREIGN_PROJECT_ID_DETECTED" in ocr_check.risk_flags:
                earned = max(0.0, earned - 5.0)
                expl += " (Foreign project ID detected on invoice)"

        earned = round(max(0.0, min(max_pts, earned)), 1)
        return ScoreFactorResult(
            factor_name="Financial evidence",
            earned_points=earned,
            maximum_points=max_pts,
            percentage=round((earned / max_pts) * 100, 1),
            explanation=expl,
            source_verification_results={
                "financial_consistency": fin_check.model_dump() if fin_check else None,
                "ocr_check": ocr_check.model_dump() if ocr_check else None,
                "document_count": len(financials),
            },
        )

    # ──────────────────────────────────────────────────────────────────────────
    # FACTOR 5: Project Identity / Details (Max 10 pts)
    # ──────────────────────────────────────────────────────────────────────────
    async def _evaluate_identity(
        self,
        db: AsyncSession,
        project: Project,
        identity_check: Optional[CheckResultSchema],
    ) -> ScoreFactorResult:
        max_pts = 10.0
        score = 0.0

        # Title & Code (+2 pts)
        if project.title and len(project.title.strip()) >= 5:
            score += 2.0

        # Description completeness (+2 pts)
        if project.description and len(project.description.strip()) >= 20:
            score += 2.0
        elif project.description:
            score += 1.0

        # Location specification (+2 pts)
        if project.latitude is not None and project.longitude is not None and project.geofence_radius:
            score += 2.0
        elif project.location_name:
            score += 1.0

        # Beneficiaries & Outcome (+2 pts)
        if project.expected_beneficiaries and project.expected_beneficiaries > 0 and project.expected_outcome:
            score += 2.0
        elif project.expected_beneficiaries or project.expected_outcome:
            score += 1.0

        # NGO verification status (+2 pts)
        ngo_status = None
        if "ngo" in project.__dict__ and project.__dict__["ngo"] is not None:
            ngo_status = getattr(project.__dict__["ngo"], "verification_status", None)
        elif project.ngo_id:
            from app.models.ngo import NGO
            ngo_obj = await db.get(NGO, project.ngo_id)
            if ngo_obj:
                ngo_status = ngo_obj.verification_status

        if ngo_status == NGOVerificationStatus.VERIFIED:
            score += 2.0
        elif ngo_status == NGOVerificationStatus.PENDING:
            score += 1.0

        earned = round(max(0.0, min(max_pts, score)), 1)
        if earned >= 9.0:
            expl = "Complete project specification and verified NGO identity."
        elif earned >= 6.0:
            expl = "Core project details provided with partial specification attributes."
        else:
            expl = "Incomplete project metadata and unverified organization status."

        return ScoreFactorResult(
            factor_name="Project identity/details",
            earned_points=earned,
            maximum_points=max_pts,
            percentage=round((earned / max_pts) * 100, 1),
            explanation=expl,
            source_verification_results={
                "project_code": project.project_code,
                "has_location_coords": (project.latitude is not None and project.longitude is not None),
                "identity_check": identity_check.model_dump() if identity_check else None,
            },
        )

    # ──────────────────────────────────────────────────────────────────────────
    # FACTOR 6: Independent Audit (Max 15 pts)
    # ──────────────────────────────────────────────────────────────────────────
    def _evaluate_audit(
        self,
        project: Project,
        audits: List[Audit],
        disputes: List[Dispute],
    ) -> ScoreFactorResult:
        max_pts = 15.0

        # Check for active dispute first
        active_dispute = next(
            (d for d in disputes if d.status in [DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW]),
            None,
        )
        is_disputed = (project.status == ProjectStatus.DISPUTED) or (active_dispute is not None)

        # Look for latest non-superseded audit decision
        latest_decision: Optional[AuditDecision] = None
        latest_audit: Optional[Audit] = None

        for audit in audits:
            for dec in sorted(audit.decisions, key=lambda d: d.decided_at, reverse=True):
                if not dec.is_superseded:
                    latest_decision = dec
                    latest_audit = audit
                    break
            if latest_decision:
                break

        if latest_decision:
            d_type = latest_decision.decision
            if d_type == AuditDecisionType.CONFIRMED:
                earned = 14.0
                expl = "Independent audit confirmed project claims and deliverables."
            elif d_type == AuditDecisionType.PARTIALLY_CONFIRMED:
                earned = 11.0
                expl = "Independent audit partially confirmed deliverables; minor items noted."
            elif d_type == AuditDecisionType.DISCREPANCY:
                earned = 4.0
                expl = "Independent audit identified material discrepancy in expenditure/telemetry."
            elif d_type == AuditDecisionType.REJECTED:
                earned = 1.0
                expl = "Independent audit rejected project verification claims."
            else:
                earned = 10.0
                expl = f"Audit decision recorded: {d_type.value}."

            if is_disputed:
                earned = min(earned, 7.0)
                reason_snippet = f": {active_dispute.reason[:60]}..." if (active_dispute and active_dispute.reason) else ""
                expl = f"[DISPUTED] Audit decision is under formal NGO dispute review{reason_snippet}."

            return ScoreFactorResult(
                factor_name="Independent audit",
                earned_points=earned,
                maximum_points=max_pts,
                percentage=round((earned / max_pts) * 100, 1),
                explanation=expl,
                source_verification_results={
                    "audit_id": str(latest_audit.id) if latest_audit else None,
                    "decision": latest_decision.decision.value,
                    "is_disputed": is_disputed,
                    "decided_at": latest_decision.decided_at.isoformat(),
                },
            )

        # No decision yet
        if audits:
            # Audit queued / in progress
            earned = 8.0
            expl = "Independent audit initiated and pending auditor review."
        else:
            # Routine project not selected for audit: neutral baseline
            earned = 10.0
            expl = "Project not selected for audit; routine verification baseline applied."

        if is_disputed:
            earned = min(earned, 6.0)
            expl = "[DISPUTED] Project has an active dispute under administrative review."

        return ScoreFactorResult(
            factor_name="Independent audit",
            earned_points=earned,
            maximum_points=max_pts,
            percentage=round((earned / max_pts) * 100, 1),
            explanation=expl,
            source_verification_results={
                "has_audit": len(audits) > 0,
                "is_disputed": is_disputed,
            },
        )


# Singleton engine instance
_engine_instance: Optional[ProjectScoreEngine] = None


def get_score_engine() -> ProjectScoreEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ProjectScoreEngine()
    return _engine_instance
