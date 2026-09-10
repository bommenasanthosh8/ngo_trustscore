"""
Risk Assessment Engine.

Identifies projects requiring additional scrutiny through 10 multi-factor risk signals:
1. Location mismatch
2. Missing timeline evidence
3. Duplicate media
4. Suspicious metadata
5. Financial inconsistency
6. Repeated failed submissions
7. High project value
8. Previous disputes
9. Unusual evidence patterns
10. Incomplete evidence

Calculates a clamped risk score (0–100), maps risk levels (LOW, MEDIUM, HIGH),
generates narrative explanations, evaluates audit triggers (HIGH_RISK, HIGH_VALUE, RANDOM_SAMPLE),
and persists audit records without directly declaring fraud.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import get_settings
from app.models.dispute import Dispute
from app.models.enums import (
    DisputeStatus,
    EvidenceType,
    FinancialConsistencyStatus,
    FinancialValidationStatus,
    ProjectType,
    RiskLevel,
    VerificationModel,
    VerificationStatus,
)
from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence
from app.models.project import Project
from app.models.risk import RiskAssessment
from app.schemas.risk import (
    AuditTriggerInfo,
    RiskAssessmentResponse,
    RiskSignalResult,
)
from app.services.financial_evidence_service import calculate_financial_consistency
from app.verification.checks.location import calculate_geodetic_distance

logger = logging.getLogger(__name__)


class RiskAssessmentEngine:
    """
    Central engine orchestrating the 10 multi-vector risk signals.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    async def evaluate_project_risk(
        self,
        db: AsyncSession,
        project: Project,
    ) -> RiskAssessmentResponse:
        """
        Evaluate all 10 risk signals for a project, clamp score to 0–100,
        generate narrative explanations, determine audit triggers, and persist result.
        """
        # 1. Fetch project evidence items
        ev_query = (
            select(Evidence)
            .where(Evidence.project_id == project.id)
            .order_by(Evidence.uploaded_at.asc())
        )
        ev_res = await db.execute(ev_query)
        evidences: List[Evidence] = list(ev_res.scalars().all())

        # 2. Fetch project financial evidence items
        fin_query = (
            select(FinancialEvidence)
            .where(FinancialEvidence.project_id == project.id)
            .order_by(FinancialEvidence.uploaded_at.asc())
        )
        fin_res = await db.execute(fin_query)
        financials: List[FinancialEvidence] = list(fin_res.scalars().all())

        # 3. Fetch project disputes
        disp_query = select(Dispute).where(Dispute.project_id == project.id)
        disp_res = await db.execute(disp_query)
        disputes: List[Dispute] = list(disp_res.scalars().all())

        # 4. Evaluate each of the 10 risk signals
        signals: List[RiskSignalResult] = []
        reasons: List[str] = []

        # Signal 1: Location mismatch (+25)
        sig_loc = self._eval_location_mismatch(project, evidences)
        signals.append(sig_loc)
        if sig_loc.triggered and sig_loc.explanation:
            reasons.append(sig_loc.explanation)

        # Signal 2: Financial inconsistency (+25)
        sig_fin = self._eval_financial_inconsistency(project, financials)
        signals.append(sig_fin)
        if sig_fin.triggered and sig_fin.explanation:
            reasons.append(sig_fin.explanation)

        # Signal 3: Duplicate media (+20)
        sig_dup = await self._eval_duplicate_media(db, project, evidences)
        signals.append(sig_dup)
        if sig_dup.triggered and sig_dup.explanation:
            reasons.append(sig_dup.explanation)

        # Signal 4: Suspicious metadata (+15)
        sig_meta = self._eval_suspicious_metadata(evidences)
        signals.append(sig_meta)
        if sig_meta.triggered and sig_meta.explanation:
            reasons.append(sig_meta.explanation)

        # Signal 5: Missing timeline evidence (+15)
        sig_tl = self._eval_missing_timeline(project, evidences)
        signals.append(sig_tl)
        if sig_tl.triggered and sig_tl.explanation:
            reasons.append(sig_tl.explanation)

        # Signal 6: Repeated failed submissions (+10)
        sig_fail = self._eval_failed_submissions(evidences, financials)
        signals.append(sig_fail)
        if sig_fail.triggered and sig_fail.explanation:
            reasons.append(sig_fail.explanation)

        # Signal 7: High project value (+10)
        sig_val = self._eval_high_project_value(project)
        signals.append(sig_val)
        if sig_val.triggered and sig_val.explanation:
            reasons.append(sig_val.explanation)

        # Signal 8: Previous disputes (+15)
        sig_disp = self._eval_previous_disputes(disputes)
        signals.append(sig_disp)
        if sig_disp.triggered and sig_disp.explanation:
            reasons.append(sig_disp.explanation)

        # Signal 9: Unusual evidence patterns (+10)
        sig_pat = self._eval_unusual_patterns(evidences)
        signals.append(sig_pat)
        if sig_pat.triggered and sig_pat.explanation:
            reasons.append(sig_pat.explanation)

        # Signal 10: Incomplete evidence (+10)
        sig_inc = self._eval_incomplete_evidence(project, evidences, financials)
        signals.append(sig_inc)
        if sig_inc.triggered and sig_inc.explanation:
            reasons.append(sig_inc.explanation)

        # 5. Calculate Clamped Risk Score (0–100)
        raw_score = sum(s.score_contribution for s in signals)
        clamped_score = round(min(100.0, max(0.0, raw_score)), 2)

        # 6. Assign Risk Level
        # 0–29 LOW, 30–59 MEDIUM, 60–100 HIGH
        if clamped_score >= 60.0:
            risk_level = RiskLevel.HIGH
        elif clamped_score >= 30.0:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        # 7. Audit Trigger Logic
        audit_triggers: List[str] = []
        audit_trigger_reasons: List[str] = []

        # Trigger A: High risk
        if risk_level == RiskLevel.HIGH:
            audit_triggers.append("HIGH_RISK_SCORE")
            audit_trigger_reasons.append(
                f"Composite risk score ({clamped_score:.0f}/100) exceeds high-risk oversight threshold (60)."
            )

        # Trigger B: High project budget
        target_budget = float(project.target_amount or project.total_budget or 0.0)
        high_val_threshold = float(self.settings.HIGH_PROJECT_VALUE_THRESHOLD)
        if target_budget >= high_val_threshold:
            audit_triggers.append("HIGH_PROJECT_VALUE")
            audit_trigger_reasons.append(
                f"Project budget ₹{target_budget:,.2f} meets or exceeds high-value audit threshold ₹{high_val_threshold:,.2f}."
            )

        # Trigger C: Random audit sampling
        # Use deterministic hash of project UUID to provide consistent sampling across runs
        sample_hash = int(hashlib.md5(str(project.id).encode("utf-8")).hexdigest()[:8], 16)
        is_sampled = (sample_hash % 100) < int(self.settings.AUDIT_RANDOM_SAMPLE_RATE * 100)
        if is_sampled:
            audit_triggers.append("RANDOM_SAMPLE_SELECTION")
            audit_trigger_reasons.append(
                f"Project selected under randomized audit quality assurance sampling ({int(self.settings.AUDIT_RANDOM_SAMPLE_RATE * 100)}% rate)."
            )

        audit_recommended = len(audit_triggers) > 0
        audit_info = AuditTriggerInfo(
            audit_recommended=audit_recommended,
            triggers=audit_triggers,
            trigger_reasons=audit_trigger_reasons,
        )

        now_utc = datetime.now(timezone.utc)

        # 8. Persist RiskAssessment record
        factors_summary = {
            "signals": [s.model_dump() for s in signals],
            "audit_triggers": audit_triggers,
            "raw_score": raw_score,
            "clamped_score": clamped_score,
            "reasons": reasons,
        }

        # Check for existing risk assessment to update or create new
        existing_res = await db.execute(
            select(RiskAssessment)
            .where(RiskAssessment.project_id == project.id)
            .order_by(RiskAssessment.assessed_at.desc())
        )
        existing_assessment = existing_res.scalars().first()

        if existing_assessment:
            existing_assessment.risk_level = risk_level
            existing_assessment.risk_score = clamped_score
            existing_assessment.factors = factors_summary
            existing_assessment.assessed_at = now_utc
        else:
            new_assessment = RiskAssessment(
                project_id=project.id,
                risk_level=risk_level,
                risk_score=clamped_score,
                factors=factors_summary,
                assessed_at=now_utc,
            )
            db.add(new_assessment)

        await db.commit()

        return RiskAssessmentResponse(
            project_id=project.id,
            project_code=project.project_code,
            risk_score=clamped_score,
            risk_level=risk_level,
            reasons=reasons,
            signals=signals,
            audit_trigger=audit_info,
            assessed_at=now_utc,
            factors_summary=factors_summary,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Individual Signal Evaluators
    # ──────────────────────────────────────────────────────────────────────────

    def _eval_location_mismatch(self, project: Project, evidences: List[Evidence]) -> RiskSignalResult:
        """Signal 1: Location mismatch (+25)"""
        weight = float(self.settings.RISK_WEIGHT_LOCATION_MISMATCH)
        geofence_radius = float(project.geofence_radius or 500.0)

        if not project.latitude or not project.longitude:
            return RiskSignalResult(
                signal_name="Location Mismatch",
                triggered=False,
                weight=weight,
                score_contribution=0.0,
                details={"reason": "Project site has no coordinates defined."},
            )

        gps_evidences = [e for e in evidences if e.latitude is not None and e.longitude is not None]
        if not gps_evidences:
            return RiskSignalResult(
                signal_name="Location Mismatch",
                triggered=False,
                weight=weight,
                score_contribution=0.0,
                details={"reason": "No evidence items have GPS telemetry to evaluate."},
            )

        max_dist = 0.0
        out_of_bounds_items = []

        for ev in gps_evidences:
            dist = calculate_geodetic_distance(
                float(project.latitude),
                float(project.longitude),
                float(ev.latitude),  # type: ignore
                float(ev.longitude),  # type: ignore
            )
            if dist > max_dist:
                max_dist = dist
            # Consider mismatch if beyond 1.2x of geofence radius
            if dist > geofence_radius * 1.2:
                out_of_bounds_items.append({
                    "evidence_id": str(ev.id),
                    "title": ev.title,
                    "distance_meters": round(dist, 1),
                })

        if out_of_bounds_items:
            dist_km = max_dist / 1000.0
            explanation = (
                f"Evidence captured {dist_km:.1f} km from registered project location "
                f"(exceeds {geofence_radius:.0f}m geofence radius)."
            )
            return RiskSignalResult(
                signal_name="Location Mismatch",
                triggered=True,
                weight=weight,
                score_contribution=weight,
                explanation=explanation,
                details={
                    "max_distance_meters": round(max_dist, 1),
                    "geofence_radius": geofence_radius,
                    "mismatched_items_count": len(out_of_bounds_items),
                },
            )

        return RiskSignalResult(
            signal_name="Location Mismatch",
            triggered=False,
            weight=weight,
            score_contribution=0.0,
            details={"max_distance_meters": round(max_dist, 1), "geofence_radius": geofence_radius},
        )

    def _eval_financial_inconsistency(
        self,
        project: Project,
        financials: List[FinancialEvidence],
    ) -> RiskSignalResult:
        """Signal 2: Financial inconsistency (+25)"""
        weight = float(self.settings.RISK_WEIGHT_FINANCIAL_DISCREPANCY)
        report = calculate_financial_consistency(project, financials)

        has_major_discrepancy = report.status == FinancialConsistencyStatus.MAJOR_DISCREPANCY
        supported_pct = (
            (report.supported_total / report.claimed_total * 100.0)
            if report.claimed_total > 0
            else 100.0
        )

        # Trigger if major discrepancy or documents support less than 85% of claimed
        if has_major_discrepancy or (report.claimed_total > 0 and supported_pct < 85.0):
            explanation = (
                f"Financial documents support only {supported_pct:.0f}% of claimed expenditure "
                f"(₹{report.supported_total:,.2f} supported vs ₹{report.claimed_total:,.2f} claimed, "
                f"difference of ₹{report.difference:,.2f})."
            )
            return RiskSignalResult(
                signal_name="Financial Inconsistency",
                triggered=True,
                weight=weight,
                score_contribution=weight,
                explanation=explanation,
                details={
                    "claimed_total": report.claimed_total,
                    "supported_total": report.supported_total,
                    "difference": report.difference,
                    "supported_percentage": round(supported_pct, 1),
                    "status": report.status.value,
                    "flags": report.flags,
                },
            )

        return RiskSignalResult(
            signal_name="Financial Inconsistency",
            triggered=False,
            weight=weight,
            score_contribution=0.0,
            details={
                "claimed_total": report.claimed_total,
                "supported_total": report.supported_total,
                "status": report.status.value,
            },
        )

    async def _eval_duplicate_media(
        self,
        db: AsyncSession,
        project: Project,
        evidences: List[Evidence],
    ) -> RiskSignalResult:
        """Signal 3: Duplicate media (+20)"""
        weight = float(self.settings.RISK_WEIGHT_DUPLICATE_MEDIA)
        hashes = [e.file_hash_sha256 for e in evidences if e.file_hash_sha256]

        if not hashes:
            return RiskSignalResult(
                signal_name="Duplicate Media",
                triggered=False,
                weight=weight,
                score_contribution=0.0,
                details={"verified_hashes": 0},
            )

        # Check cross-project duplicate reuse
        cross_q = select(Evidence).where(
            Evidence.file_hash_sha256.in_(hashes),
            Evidence.project_id != project.id,
        )
        cross_res = await db.execute(cross_q)
        cross_dupes = cross_res.scalars().all()

        if cross_dupes:
            other_pids = list({str(d.project_id) for d in cross_dupes})
            explanation = (
                f"Similar media or identical cryptographic hash detected across {len(other_pids)} other project(s) "
                f"(cross-project reuse flag)."
            )
            return RiskSignalResult(
                signal_name="Duplicate Media",
                triggered=True,
                weight=weight,
                score_contribution=weight,
                explanation=explanation,
                details={
                    "cross_project_duplicate_count": len(cross_dupes),
                    "matched_project_ids": other_pids[:3],
                },
            )

        # Check internal duplicate files
        hash_counts: Dict[str, int] = {}
        for h in hashes:
            hash_counts[h] = hash_counts.get(h, 0) + 1
        internal_dupes = sum(1 for c in hash_counts.values() if c > 1)

        if internal_dupes > 0:
            explanation = f"{internal_dupes} duplicate media file(s) submitted repeatedly within this project."
            return RiskSignalResult(
                signal_name="Duplicate Media",
                triggered=True,
                weight=weight,
                score_contribution=weight,
                explanation=explanation,
                details={"internal_duplicates": internal_dupes},
            )

        return RiskSignalResult(
            signal_name="Duplicate Media",
            triggered=False,
            weight=weight,
            score_contribution=0.0,
            details={"unique_media_count": len(hashes)},
        )

    def _eval_suspicious_metadata(self, evidences: List[Evidence]) -> RiskSignalResult:
        """Signal 4: Suspicious metadata (+15)"""
        weight = float(self.settings.RISK_WEIGHT_SUSPICIOUS_METADATA)
        editing_tools = ["photoshop", "gimp", "canva", "picsart", "lightroom", "pixlr", "snapseed"]
        suspicious_found = []

        for ev in evidences:
            meta = ev.metadata_summary or {}
            software = str(meta.get("software", "")).lower()
            detected = [tool for tool in editing_tools if tool in software]
            if detected:
                suspicious_found.append({
                    "evidence_id": str(ev.id),
                    "software": software,
                    "tools": detected,
                })

        if suspicious_found:
            first_tool = suspicious_found[0]["software"]
            explanation = (
                f"Metadata indicates external photo-editing software ({first_tool}) was utilized "
                f"on {len(suspicious_found)} submitted evidence image(s)."
            )
            return RiskSignalResult(
                signal_name="Suspicious Metadata",
                triggered=True,
                weight=weight,
                score_contribution=weight,
                explanation=explanation,
                details={"suspicious_count": len(suspicious_found), "items": suspicious_found},
            )

        return RiskSignalResult(
            signal_name="Suspicious Metadata",
            triggered=False,
            weight=weight,
            score_contribution=0.0,
            details={"suspicious_count": 0},
        )

    def _eval_missing_timeline(self, project: Project, evidences: List[Evidence]) -> RiskSignalResult:
        """Signal 5: Missing timeline evidence (+15)"""
        weight = float(self.settings.RISK_WEIGHT_MISSING_TIMELINE)
        model = project.verification_model or VerificationModel.PERMANENT
        category = project.project_type

        is_permanent = (
            model == VerificationModel.PERMANENT or
            category in (ProjectType.INFRASTRUCTURE, ProjectType.WATER_AND_SANITATION, ProjectType.SANITATION)
        )

        if not is_permanent:
            return RiskSignalResult(
                signal_name="Missing Timeline",
                triggered=False,
                weight=weight,
                score_contribution=0.0,
                details={"model": model.value},
            )

        submitted_types: Set[str] = {e.evidence_type.value for e in evidences}
        required_permanent = ["BEFORE", "PROGRESS", "COMPLETION"]
        missing = [r for r in required_permanent if r not in submitted_types]

        if missing:
            explanation = (
                f"Permanent project lifecycle missing essential milestone stage(s): {', '.join(missing)}."
            )
            return RiskSignalResult(
                signal_name="Missing Timeline",
                triggered=True,
                weight=weight,
                score_contribution=weight,
                explanation=explanation,
                details={"missing_stages": missing, "submitted_stages": list(submitted_types)},
            )

        return RiskSignalResult(
            signal_name="Missing Timeline",
            triggered=False,
            weight=weight,
            score_contribution=0.0,
            details={"status": "All required timeline milestones present"},
        )

    def _eval_failed_submissions(
        self,
        evidences: List[Evidence],
        financials: List[FinancialEvidence],
    ) -> RiskSignalResult:
        """Signal 6: Repeated failed submissions (+10)"""
        weight = float(self.settings.RISK_WEIGHT_FAILED_SUBMISSIONS)
        failed_ev = [
            e for e in evidences
            if e.verification_status in (VerificationStatus.FLAGGED, VerificationStatus.REJECTED)
        ]
        failed_fin = [
            f for f in financials
            if f.validation_status in (
                FinancialValidationStatus.AMOUNT_MISMATCH,
                FinancialValidationStatus.DUPLICATE_DOCUMENT,
                FinancialValidationStatus.SUSPICIOUS_REPEATED,
            )
        ]

        total_failed = len(failed_ev) + len(failed_fin)
        if total_failed >= 2:
            explanation = (
                f"Multiple submission failures recorded: {total_failed} evidence and/or financial item(s) "
                f"flagged during previous verification audits."
            )
            return RiskSignalResult(
                signal_name="Repeated Failed Submissions",
                triggered=True,
                weight=weight,
                score_contribution=weight,
                explanation=explanation,
                details={
                    "failed_evidence_count": len(failed_ev),
                    "failed_financial_count": len(failed_fin),
                    "total_failed": total_failed,
                },
            )

        return RiskSignalResult(
            signal_name="Repeated Failed Submissions",
            triggered=False,
            weight=weight,
            score_contribution=0.0,
            details={"failed_count": total_failed},
        )

    def _eval_high_project_value(self, project: Project) -> RiskSignalResult:
        """Signal 7: High project value (+10)"""
        weight = float(self.settings.RISK_WEIGHT_HIGH_PROJECT_VALUE)
        target = float(project.target_amount or project.total_budget or 0.0)
        threshold = float(self.settings.HIGH_PROJECT_VALUE_THRESHOLD)

        if target >= threshold:
            explanation = (
                f"High financial exposure: project target budget of ₹{target:,.2f} meets or exceeds "
                f"the platform high-scrutiny threshold (₹{threshold:,.2f})."
            )
            return RiskSignalResult(
                signal_name="High Project Value",
                triggered=True,
                weight=weight,
                score_contribution=weight,
                explanation=explanation,
                details={"target_amount": target, "threshold": threshold},
            )

        return RiskSignalResult(
            signal_name="High Project Value",
            triggered=False,
            weight=weight,
            score_contribution=0.0,
            details={"target_amount": target, "threshold": threshold},
        )

    def _eval_previous_disputes(self, disputes: List[Dispute]) -> RiskSignalResult:
        """Signal 8: Previous disputes (+15)"""
        weight = float(self.settings.RISK_WEIGHT_PREVIOUS_DISPUTES)
        active_disputes = [
            d for d in disputes
            if d.status in (DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW)
        ]

        if disputes:
            status_desc = f"{len(active_disputes)} active" if active_disputes else f"{len(disputes)} historical"
            explanation = (
                f"{len(disputes)} donor or stakeholder dispute(s) recorded against this project ({status_desc})."
            )
            return RiskSignalResult(
                signal_name="Previous Disputes",
                triggered=True,
                weight=weight,
                score_contribution=weight,
                explanation=explanation,
                details={
                    "total_disputes": len(disputes),
                    "active_disputes": len(active_disputes),
                    "reasons": [d.reason for d in disputes[:3]],
                },
            )

        return RiskSignalResult(
            signal_name="Previous Disputes",
            triggered=False,
            weight=weight,
            score_contribution=0.0,
            details={"dispute_count": 0},
        )

    def _eval_unusual_patterns(self, evidences: List[Evidence]) -> RiskSignalResult:
        """Signal 9: Unusual evidence patterns (+10)"""
        weight = float(self.settings.RISK_WEIGHT_UNUSUAL_PATTERNS)
        if len(evidences) < 3:
            return RiskSignalResult(
                signal_name="Unusual Evidence Patterns",
                triggered=False,
                weight=weight,
                score_contribution=0.0,
                details={"items_count": len(evidences)},
            )

        # Detect rapid burst submissions (< 60 seconds between 3 or more uploads)
        upload_times = sorted([e.uploaded_at for e in evidences if e.uploaded_at])
        burst_detected = False
        burst_count = 0

        for i in range(len(upload_times) - 2):
            diff = (upload_times[i + 2] - upload_times[i]).total_seconds()
            if diff < 60.0:  # 3 items uploaded in under 60 seconds
                burst_detected = True
                burst_count += 1

        if burst_detected:
            explanation = (
                f"Unusual submission velocity: batch upload burst detected with multiple evidence items "
                f"submitted within seconds of each other."
            )
            return RiskSignalResult(
                signal_name="Unusual Evidence Patterns",
                triggered=True,
                weight=weight,
                score_contribution=weight,
                explanation=explanation,
                details={"burst_events": burst_count, "evaluated_items": len(evidences)},
            )

        return RiskSignalResult(
            signal_name="Unusual Evidence Patterns",
            triggered=False,
            weight=weight,
            score_contribution=0.0,
            details={"evaluated_items": len(evidences)},
        )

    def _eval_incomplete_evidence(
        self,
        project: Project,
        evidences: List[Evidence],
        financials: List[FinancialEvidence],
    ) -> RiskSignalResult:
        """Signal 10: Incomplete evidence (+10)"""
        weight = float(self.settings.RISK_WEIGHT_INCOMPLETE_EVIDENCE)
        category = project.project_type or ProjectType.OTHER

        total_evidence = len(evidences) + len(financials)
        if total_evidence == 0:
            explanation = (
                f"Project has zero submitted evidence records for category '{category.value}'. "
                f"Verification requirements unfulfilled."
            )
            return RiskSignalResult(
                signal_name="Incomplete Evidence",
                triggered=True,
                weight=weight,
                score_contribution=weight,
                explanation=explanation,
                details={"total_evidence": 0, "category": category.value},
            )

        # Permanent projects require at least 3 distinct evidence items
        if category in (ProjectType.INFRASTRUCTURE, ProjectType.WATER_AND_SANITATION) and len(evidences) < 2:
            explanation = (
                f"Insufficient evidence volume: only {len(evidences)} item(s) submitted for infrastructure category."
            )
            return RiskSignalResult(
                signal_name="Incomplete Evidence",
                triggered=True,
                weight=weight,
                score_contribution=weight,
                explanation=explanation,
                details={"evidence_count": len(evidences), "financial_count": len(financials)},
            )

        return RiskSignalResult(
            signal_name="Incomplete Evidence",
            triggered=False,
            weight=weight,
            score_contribution=0.0,
            details={"total_evidence": total_evidence},
        )


# Global default engine instance
default_risk_engine = RiskAssessmentEngine()


def get_risk_engine() -> RiskAssessmentEngine:
    """Return default RiskAssessmentEngine instance."""
    return default_risk_engine
