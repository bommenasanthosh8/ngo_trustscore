"""
Integrity & Anti-Manipulation Service.

Evaluates projects against 10 critical fraud and manipulation threat vectors:
1. Old/reused photos (EXIF timeline analysis & pre-dating checks)
2. Duplicate evidence (intra-project SHA-256 collision detection)
3. Fake GPS (geofence boundaries & telemetry analysis - probabilistic signal)
4. Manipulated media (editing software metadata & artifact heuristics - risk signal)
5. Fake projects (unverified NGO profiles, zero beneficiaries, unanchored sites)
6. Repeated upload attempts (failed submission velocity & revision churning)
7. Artificial project inflation (budget anomalies & high-value scrutiny thresholds)
8. Financial inconsistencies (OCR mismatch, deficit support, duplicate invoices)
9. Auditor manipulation (tamper-evident audit decisions, immutable logs, score protection)
10. Evidence deletion (append-only ledger enforcement, zero-deletion policy)

CRITICAL INVARIANTS:
- GPS spoofing cannot be completely prevented by prototype software -> treated as a corroborating signal.
  DO NOT claim: "GPS guarantees authenticity."
- AI image/metadata analysis is a heuristic risk signal, NOT definitive proof.
- Suspicious behavior is made visible to auditors via prominent Integrity Flags.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import (
    FinancialConsistencyStatus,
    FinancialValidationStatus,
    LocationStatus,
    ProjectType,
    RiskLevel,
    VerificationModel,
    VerificationStatus,
)
from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence
from app.models.ngo import NGO
from app.models.project import Project
from app.models.risk import RiskAssessment
from app.schemas.integrity import (
    IntegrityFlagItem,
    ProjectIntegrityReportResponse,
    SubmissionAttemptSummary,
    ThreatEvaluation,
)
from app.services.financial_evidence_service import calculate_financial_consistency
from app.verification.checks.location import calculate_geodetic_distance

logger = logging.getLogger(__name__)

GPS_DISCLAIMER = (
    "GPS coordinates are evaluated as a corroborating signal only. Prototype software "
    "cannot completely prevent hardware-level GPS spoofing. GPS does not guarantee physical authenticity."
)

AI_ANALYSIS_DISCLAIMER = (
    "Automated media and metadata analysis are heuristic risk indicators, not definitive proof of manipulation."
)

PLATFORM_DISCLAIMER = (
    "The anti-manipulation layer flags suspicious anomalies for human auditor review rather than silently accepting submissions."
)


class IntegrityService:
    """Orchestrates comprehensive 10-threat anti-manipulation evaluation."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def generate_project_integrity_report(
        self,
        db: AsyncSession,
        project: Project,
    ) -> ProjectIntegrityReportResponse:
        """
        Evaluate project across all 10 threat vectors, generate active integrity warning flags,
        and assemble submission history forensics.
        """
        # 1. Fetch project's evidences and financial evidence
        ev_q = (
            select(Evidence)
            .where(Evidence.project_id == project.id)
            .order_by(Evidence.uploaded_at.asc())
        )
        ev_res = await db.execute(ev_q)
        evidences: List[Evidence] = list(ev_res.scalars().all())

        fin_q = (
            select(FinancialEvidence)
            .where(FinancialEvidence.project_id == project.id)
            .order_by(FinancialEvidence.uploaded_at.asc())
        )
        fin_res = await db.execute(fin_q)
        financials: List[FinancialEvidence] = list(fin_res.scalars().all())

        # 2. Fetch NGO information
        ngo_q = select(NGO).where(NGO.id == project.ngo_id)
        ngo_res = await db.execute(ngo_q)
        ngo: Optional[NGO] = ngo_res.scalars().first()

        # 3. Fetch latest RiskAssessment
        risk_q = (
            select(RiskAssessment)
            .where(RiskAssessment.project_id == project.id)
            .order_by(RiskAssessment.assessed_at.desc())
        )
        risk_res = await db.execute(risk_q)
        latest_risk = risk_res.scalars().first()

        # 4. Evaluate each of the 10 threat vectors
        threats: List[ThreatEvaluation] = []
        active_flags: List[IntegrityFlagItem] = []

        # Threat 1: Old/reused photos
        t1, f1 = await self._eval_threat_old_reused_photos(db, project, evidences)
        threats.append(t1)
        if f1:
            active_flags.extend(f1)

        # Threat 2: Duplicate evidence
        t2, f2 = self._eval_threat_duplicate_evidence(evidences, financials)
        threats.append(t2)
        if f2:
            active_flags.extend(f2)

        # Threat 3: Fake GPS (Signal only)
        t3, f3 = self._eval_threat_fake_gps(project, evidences)
        threats.append(t3)
        if f3:
            active_flags.extend(f3)

        # Threat 4: Manipulated media (AI/heuristic signal)
        t4, f4 = self._eval_threat_manipulated_media(evidences)
        threats.append(t4)
        if f4:
            active_flags.extend(f4)

        # Threat 5: Fake projects
        t5, f5 = self._eval_threat_fake_projects(project, ngo)
        threats.append(t5)
        if f5:
            active_flags.extend(f5)

        # Threat 6: Repeated upload attempts
        t6, f6 = self._eval_threat_repeated_upload_attempts(evidences, financials)
        threats.append(t6)
        if f6:
            active_flags.extend(f6)

        # Threat 7: Artificial project inflation
        t7, f7 = self._eval_threat_project_inflation(project)
        threats.append(t7)
        if f7:
            active_flags.extend(f7)

        # Threat 8: Financial inconsistencies
        t8, f8 = self._eval_threat_financial_inconsistencies(project, financials)
        threats.append(t8)
        if f8:
            active_flags.extend(f8)

        # Threat 9: Auditor manipulation (System architecture enforcement)
        t9 = self._eval_threat_auditor_manipulation()
        threats.append(t9)

        # Threat 10: Evidence deletion (Append-only ledger enforcement)
        t10 = self._eval_threat_evidence_deletion(evidences)
        threats.append(t10)

        # 5. Compile submission attempt history
        submission_summary = self._compile_submission_summary(evidences, financials)

        # 6. Determine composite risk level and score
        risk_score = float(latest_risk.risk_score) if latest_risk else 0.0
        risk_level = latest_risk.risk_level.value if latest_risk else "LOW"

        # Determine if audit is recommended based on active flags or high-level risk
        has_high_flags = any(flag.severity == "HIGH" for flag in active_flags)
        audit_recommended = has_high_flags or risk_score >= 60.0

        return ProjectIntegrityReportResponse(
            project_id=project.id,
            project_code=project.project_code,
            project_title=project.title,
            overall_risk_level=risk_level,
            risk_score=risk_score,
            audit_recommended=audit_recommended,
            active_flags=active_flags,
            threats_matrix=threats,
            submission_history=submission_summary,
            disclaimers=[
                GPS_DISCLAIMER,
                AI_ANALYSIS_DISCLAIMER,
                PLATFORM_DISCLAIMER,
            ],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Threat Vector Evaluators
    # ──────────────────────────────────────────────────────────────────────────

    async def _eval_threat_old_reused_photos(
        self,
        db: AsyncSession,
        project: Project,
        evidences: List[Evidence],
    ) -> Tuple[ThreatEvaluation, List[IntegrityFlagItem]]:
        """Threat 1: Old/reused photos across different projects or historical periods."""
        flags: List[IntegrityFlagItem] = []
        hashes = [e.file_hash_sha256 for e in evidences if e.file_hash_sha256]

        cross_project_dupes: List[Evidence] = []
        if hashes:
            cross_q = select(Evidence).where(
                Evidence.file_hash_sha256.in_(hashes),
                Evidence.project_id != project.id,
            )
            cross_res = await db.execute(cross_q)
            cross_project_dupes = list(cross_res.scalars().all())

        # Check for evidence captured prior to project start date
        predated_items = []
        if project.start_date:
            for ev in evidences:
                if ev.captured_at:
                    cap_dt = ev.captured_at if ev.captured_at.tzinfo else ev.captured_at.replace(tzinfo=timezone.utc)
                    p_start = project.start_date if project.start_date.tzinfo else project.start_date.replace(tzinfo=timezone.utc)
                    if cap_dt < p_start:
                        predated_items.append({
                            "evidence_id": str(ev.id),
                            "title": ev.title,
                            "captured_at": ev.captured_at.isoformat(),
                            "project_start": project.start_date.isoformat(),
                        })

        triggered = bool(cross_project_dupes or predated_items)
        severity = "HIGH" if cross_project_dupes else ("MEDIUM" if predated_items else "LOW")
        status = "FLAGGED" if cross_project_dupes else ("WARNING" if predated_items else "CLEAR")

        details: Dict[str, Any] = {
            "cross_project_reused_count": len(cross_project_dupes),
            "predated_evidence_count": len(predated_items),
        }

        if cross_project_dupes:
            explanation = (
                f"Cryptographic SHA-256 match detected: {len(cross_project_dupes)} submitted image(s) "
                f"were previously submitted to other projects in the registry."
            )
            flags.append(
                IntegrityFlagItem(
                    severity="HIGH",
                    title="Evidence reused across projects",
                    explanation=explanation,
                    signal_code="CROSS_PROJECT_REUSE",
                )
            )
        elif predated_items:
            explanation = (
                f"{len(predated_items)} image(s) have EXIF capture timestamps that predate "
                f"the registered project kickoff date ({project.start_date.strftime('%Y-%m-%d')})."
            )
            flags.append(
                IntegrityFlagItem(
                    severity="MEDIUM",
                    title="Evidence predates project start",
                    explanation=explanation,
                    signal_code="PREDATED_EVIDENCE",
                )
            )
        else:
            explanation = "No cross-project hash collisions or pre-dating timestamp anomalies detected."

        eval_res = ThreatEvaluation(
            threat_number=1,
            threat_name="Old/reused photos",
            severity=severity,
            triggered=triggered,
            status=status,
            explanation=explanation,
            is_probabilistic_signal=False,
            details=details,
        )
        return eval_res, flags

    def _eval_threat_duplicate_evidence(
        self,
        evidences: List[Evidence],
        financials: List[FinancialEvidence],
    ) -> Tuple[ThreatEvaluation, List[IntegrityFlagItem]]:
        """Threat 2: Duplicate evidence submitted within the same project."""
        flags: List[IntegrityFlagItem] = []
        ev_hashes = [e.file_hash_sha256 for e in evidences if e.file_hash_sha256]

        hash_counts: Dict[str, int] = {}
        for h in ev_hashes:
            hash_counts[h] = hash_counts.get(h, 0) + 1
        internal_ev_dupes = sum(1 for c in hash_counts.values() if c > 1)

        # Check duplicate financial invoices
        inv_counts: Dict[str, int] = {}
        for f in financials:
            if f.invoice_number:
                norm_inv = f.invoice_number.strip().upper()
                inv_counts[norm_inv] = inv_counts.get(norm_inv, 0) + 1
        dup_invoices = sum(1 for c in inv_counts.values() if c > 1)

        triggered = internal_ev_dupes > 0 or dup_invoices > 0
        severity = "HIGH" if triggered else "LOW"
        status = "FLAGGED" if triggered else "CLEAR"

        if triggered:
            explanation = (
                f"Identical evidence detected within project: {internal_ev_dupes} duplicate photo hash(es) "
                f"and {dup_invoices} duplicate financial invoice number(s)."
            )
            flags.append(
                IntegrityFlagItem(
                    severity="HIGH",
                    title="Duplicate evidence within project",
                    explanation=explanation,
                    signal_code="INTERNAL_DUPLICATE",
                )
            )
        else:
            explanation = "All submitted evidence files and invoice numbers are unique within this project."

        eval_res = ThreatEvaluation(
            threat_number=2,
            threat_name="Duplicate evidence",
            severity=severity,
            triggered=triggered,
            status=status,
            explanation=explanation,
            is_probabilistic_signal=False,
            details={
                "duplicate_media_hashes": internal_ev_dupes,
                "duplicate_invoices": dup_invoices,
            },
        )
        return eval_res, flags

    def _eval_threat_fake_gps(
        self,
        project: Project,
        evidences: List[Evidence],
    ) -> Tuple[ThreatEvaluation, List[IntegrityFlagItem]]:
        """Threat 3: Fake GPS / location manipulation (Treated strictly as a signal)."""
        flags: List[IntegrityFlagItem] = []
        geofence = float(project.geofence_radius or 500.0)

        if not project.latitude or not project.longitude:
            return ThreatEvaluation(
                threat_number=3,
                threat_name="Fake GPS",
                severity="LOW",
                triggered=False,
                status="CLEAR",
                explanation="Project has no reference coordinates configured for geofence validation.",
                is_probabilistic_signal=True,
                disclaimer=GPS_DISCLAIMER,
                details={"has_coordinates": False},
            ), flags

        gps_ev = [e for e in evidences if e.latitude is not None and e.longitude is not None]
        if not gps_ev:
            return ThreatEvaluation(
                threat_number=3,
                threat_name="Fake GPS",
                severity="LOW",
                triggered=False,
                status="CLEAR",
                explanation="No submitted evidence items contain GPS metadata to cross-reference.",
                is_probabilistic_signal=True,
                disclaimer=GPS_DISCLAIMER,
                details={"gps_items_count": 0},
            ), flags

        mismatches = []
        max_distance = 0.0
        for e in gps_ev:
            dist = calculate_geodetic_distance(
                float(project.latitude),
                float(project.longitude),
                float(e.latitude),  # type: ignore
                float(e.longitude),  # type: ignore
            )
            if dist > max_distance:
                max_distance = dist
            if dist > geofence * 1.2:
                mismatches.append({
                    "evidence_id": str(e.id),
                    "distance_meters": round(dist, 1),
                })

        triggered = len(mismatches) > 0
        severity = "HIGH" if triggered else "LOW"
        status = "FLAGGED" if triggered else "CLEAR"

        if triggered:
            dist_km = max_distance / 1000.0
            explanation = (
                f"Location mismatch detected: {len(mismatches)} item(s) captured up to {dist_km:.1f} km "
                f"away from registered site (exceeds {geofence:.0f}m geofence radius). "
                f"Corroborating signal flagged for auditor review."
            )
            flags.append(
                IntegrityFlagItem(
                    severity="HIGH",
                    title="Location mismatch",
                    explanation=explanation,
                    signal_code="LOCATION_MISMATCH",
                )
            )
        else:
            explanation = f"GPS coordinates corroborate site boundary (maximum offset {max_distance:.1f}m within geofence)."

        eval_res = ThreatEvaluation(
            threat_number=3,
            threat_name="Fake GPS",
            severity=severity,
            triggered=triggered,
            status=status,
            explanation=explanation,
            is_probabilistic_signal=True,
            disclaimer=GPS_DISCLAIMER,
            details={
                "mismatch_count": len(mismatches),
                "max_offset_meters": round(max_distance, 1),
                "geofence_radius": geofence,
            },
        )
        return eval_res, flags

    def _eval_threat_manipulated_media(
        self,
        evidences: List[Evidence],
    ) -> Tuple[ThreatEvaluation, List[IntegrityFlagItem]]:
        """Threat 4: Manipulated media (AI image/metadata heuristic signal)."""
        flags: List[IntegrityFlagItem] = []
        editing_tools = ["photoshop", "gimp", "canva", "picsart", "lightroom", "pixlr", "snapseed"]
        detected = []

        for e in evidences:
            meta = e.metadata_summary or {}
            software = str(meta.get("software", "")).lower()
            found = [t for t in editing_tools if t in software]
            if found:
                detected.append({
                    "evidence_id": str(e.id),
                    "software": software,
                    "tool": found[0],
                })

        triggered = len(detected) > 0
        severity = "MEDIUM" if triggered else "LOW"
        status = "WARNING" if triggered else "CLEAR"

        if triggered:
            tools_str = ", ".join(list({d['tool'].capitalize() for d in detected}))
            explanation = (
                f"Media editing software detected ({tools_str}) on {len(detected)} image(s). "
                f"Automated heuristic indicates possible retouching, cropping, or composite alteration."
            )
            flags.append(
                IntegrityFlagItem(
                    severity="MEDIUM",
                    title="Edited media detected",
                    explanation=explanation,
                    signal_code="MANIPULATED_MEDIA",
                )
            )
        else:
            explanation = "No external image modification software signatures detected in media metadata."

        eval_res = ThreatEvaluation(
            threat_number=4,
            threat_name="Manipulated media",
            severity=severity,
            triggered=triggered,
            status=status,
            explanation=explanation,
            is_probabilistic_signal=True,
            disclaimer=AI_ANALYSIS_DISCLAIMER,
            details={"suspicious_metadata_count": len(detected)},
        )
        return eval_res, flags

    def _eval_threat_fake_projects(
        self,
        project: Project,
        ngo: Optional[NGO],
    ) -> Tuple[ThreatEvaluation, List[IntegrityFlagItem]]:
        """Threat 5: Fake projects (Unverified NGO profile or bogus beneficiary claims)."""
        flags: List[IntegrityFlagItem] = []
        issues = []

        if ngo and getattr(ngo, "verification_status", None) == "REJECTED":
            issues.append("Operating NGO is marked REJECTED by compliance administration.")
        bens = getattr(project, "expected_beneficiaries", None)
        if bens is not None and bens <= 0:
            issues.append("Project claims 0 beneficiaries.")
        if not project.location_name and not (project.latitude and project.longitude):
            issues.append("Project has no physical site or geographic location declared.")

        triggered = len(issues) > 0
        severity = "HIGH" if (ngo and getattr(ngo, "verification_status", None) == "REJECTED") else ("MEDIUM" if triggered else "LOW")
        status = "FLAGGED" if severity == "HIGH" else ("WARNING" if triggered else "CLEAR")

        if triggered:
            explanation = "; ".join(issues)
            flags.append(
                IntegrityFlagItem(
                    severity=severity,
                    title="Project authenticity warning",
                    explanation=explanation,
                    signal_code="FAKE_PROJECT_SUSPICION",
                )
            )
        else:
            explanation = "Project entity is backed by an active NGO profile with geographic anchoring."

        eval_res = ThreatEvaluation(
            threat_number=5,
            threat_name="Fake projects",
            severity=severity,
            triggered=triggered,
            status=status,
            explanation=explanation,
            is_probabilistic_signal=False,
            details={"issues": issues},
        )
        return eval_res, flags

    def _eval_threat_repeated_upload_attempts(
        self,
        evidences: List[Evidence],
        financials: List[FinancialEvidence],
    ) -> Tuple[ThreatEvaluation, List[IntegrityFlagItem]]:
        """Threat 6: Repeated upload attempts and submission velocity anomalies."""
        flags: List[IntegrityFlagItem] = []
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
        superseded_items = [e for e in evidences if e.supersedes_id is not None]

        triggered = total_failed >= 2 or len(superseded_items) >= 3
        severity = "MEDIUM" if triggered else "LOW"
        status = "WARNING" if triggered else "CLEAR"

        if triggered:
            explanation = (
                f"Elevated submission churn: {total_failed} rejected/flagged submission(s) and "
                f"{len(superseded_items)} superseded revision attempt(s) recorded."
            )
            flags.append(
                IntegrityFlagItem(
                    severity="MEDIUM",
                    title="Repeated upload attempts",
                    explanation=explanation,
                    signal_code="REPEATED_ATTEMPTS",
                )
            )
        else:
            explanation = "Submission attempt rate and revision velocity remain within normal operational bounds."

        eval_res = ThreatEvaluation(
            threat_number=6,
            threat_name="Repeated upload attempts",
            severity=severity,
            triggered=triggered,
            status=status,
            explanation=explanation,
            is_probabilistic_signal=False,
            details={
                "failed_evidence_count": len(failed_ev),
                "failed_financial_count": len(failed_fin),
                "superseded_count": len(superseded_items),
            },
        )
        return eval_res, flags

    def _eval_threat_project_inflation(
        self,
        project: Project,
    ) -> Tuple[ThreatEvaluation, List[IntegrityFlagItem]]:
        """Threat 7: Artificial project inflation (Target budget scrutiny & high value)."""
        flags: List[IntegrityFlagItem] = []
        target = float(project.target_amount or project.total_budget or 0.0)
        threshold = float(self.settings.HIGH_PROJECT_VALUE_THRESHOLD)

        is_high_value = target >= threshold
        beneficiaries = getattr(project, "expected_beneficiaries", None) or 0
        cost_per_beneficiary = (target / beneficiaries) if beneficiaries > 0 else 0.0
        is_ratio_anomaly = beneficiaries > 0 and cost_per_beneficiary > 100_000.0

        triggered = is_high_value or is_ratio_anomaly
        severity = "HIGH" if is_ratio_anomaly else ("MEDIUM" if is_high_value else "LOW")
        status = "FLAGGED" if severity == "HIGH" else ("WARNING" if is_high_value else "CLEAR")

        if is_ratio_anomaly:
            explanation = (
                f"Abnormal unit expenditure: ₹{cost_per_beneficiary:,.2f} per beneficiary "
                f"(₹{target:,.2f} budget for {beneficiaries} beneficiaries) triggers artificial inflation alert."
            )
            flags.append(
                IntegrityFlagItem(
                    severity="HIGH",
                    title="Suspicious project budget inflation",
                    explanation=explanation,
                    signal_code="PROJECT_INFLATION_RATIO",
                )
            )
        elif is_high_value:
            explanation = (
                f"High-exposure initiative: budget of ₹{target:,.2f} meets platform mandatory "
                f"audit priority threshold (₹{threshold:,.2f})."
            )
            flags.append(
                IntegrityFlagItem(
                    severity="MEDIUM",
                    title="High financial exposure",
                    explanation=explanation,
                    signal_code="HIGH_PROJECT_VALUE",
                )
            )
        else:
            explanation = "Project budget scale matches standard category benchmarks."

        eval_res = ThreatEvaluation(
            threat_number=7,
            threat_name="Artificial project inflation",
            severity=severity,
            triggered=triggered,
            status=status,
            explanation=explanation,
            is_probabilistic_signal=False,
            details={
                "target_amount": target,
                "high_value_threshold": threshold,
                "cost_per_beneficiary": round(cost_per_beneficiary, 2),
            },
        )
        return eval_res, flags

    def _eval_threat_financial_inconsistencies(
        self,
        project: Project,
        financials: List[FinancialEvidence],
    ) -> Tuple[ThreatEvaluation, List[IntegrityFlagItem]]:
        """Threat 8: Financial inconsistencies between claimed budget and receipts."""
        flags: List[IntegrityFlagItem] = []
        report = calculate_financial_consistency(project, financials)

        has_major_discrepancy = report.status == FinancialConsistencyStatus.MAJOR_DISCREPANCY
        supported_pct = (
            (report.supported_total / report.claimed_total * 100.0)
            if report.claimed_total > 0
            else 100.0
        )
        has_deficit = report.claimed_total > 0 and supported_pct < 85.0

        triggered = has_major_discrepancy or has_deficit
        severity = "HIGH" if triggered else "LOW"
        status = "FLAGGED" if triggered else "CLEAR"

        if triggered:
            explanation = (
                f"Financial discrepancy: OCR-validated receipts support only {supported_pct:.1f}% "
                f"of claimed expenditure (₹{report.supported_total:,.2f} supported vs ₹{report.claimed_total:,.2f} claimed, "
                f"unsupported variance of ₹{report.difference:,.2f})."
            )
            flags.append(
                IntegrityFlagItem(
                    severity="HIGH",
                    title="Financial discrepancy",
                    explanation=explanation,
                    signal_code="FINANCIAL_DISCREPANCY",
                )
            )
        else:
            explanation = f"Financial receipts reconcile with claimed expenditure ({supported_pct:.1f}% supported)."

        eval_res = ThreatEvaluation(
            threat_number=8,
            threat_name="Financial inconsistencies",
            severity=severity,
            triggered=triggered,
            status=status,
            explanation=explanation,
            is_probabilistic_signal=False,
            details={
                "claimed_total": report.claimed_total,
                "supported_total": report.supported_total,
                "unsupported_difference": report.difference,
                "supported_percentage": round(supported_pct, 1),
                "status": report.status.value,
            },
        )
        return eval_res, flags

    def _eval_threat_auditor_manipulation(self) -> ThreatEvaluation:
        """Threat 9: Auditor manipulation (Immutable decisions & score protection)."""
        # Architectural guarantee: decisions are write-once with mandatory finding reason;
        # score recalculated by backend engine only; direct score manipulation is rejected.
        return ThreatEvaluation(
            threat_number=9,
            threat_name="Auditor manipulation",
            severity="LOW",
            triggered=False,
            status="CLEAR",
            explanation=(
                "Auditor decisions are write-once, immutable, and require mandatory finding justifications. "
                "Auditors are strictly barred from directly altering transparency scores; all recalculations "
                "are deterministic and emitted to immutable ActivityLogs."
            ),
            is_probabilistic_signal=False,
            details={"immutable_records_enforced": True, "direct_score_override_allowed": False},
        )

    def _eval_threat_evidence_deletion(
        self,
        evidences: List[Evidence],
    ) -> ThreatEvaluation:
        """Threat 10: Evidence deletion (Append-only storage & immutable revision history)."""
        # Architectural guarantee: database schema and APIs provide no DELETE operation for evidence.
        return ThreatEvaluation(
            threat_number=10,
            threat_name="Evidence deletion",
            severity="LOW",
            triggered=False,
            status="CLEAR",
            explanation=(
                "Platform enforces an append-only ledger policy. No delete operations exist for evidence or financial "
                "records. Corrected submissions supersede rather than replace previous entries, preserving complete forensic audit trails."
            ),
            is_probabilistic_signal=False,
            details={"append_only_enforced": True, "delete_endpoints_enabled": False},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Helper: Submission Attempt Forensics
    # ──────────────────────────────────────────────────────────────────────────

    def _compile_submission_summary(
        self,
        evidences: List[Evidence],
        financials: List[FinancialEvidence],
    ) -> SubmissionAttemptSummary:
        """Compile statistical breakdown of evidence and financial submissions."""
        total = len(evidences) + len(financials)

        verified = sum(1 for e in evidences if e.verification_status == VerificationStatus.VERIFIED)
        verified += sum(1 for f in financials if f.validation_status == FinancialValidationStatus.VALID)

        failed = sum(1 for e in evidences if e.verification_status in (VerificationStatus.FLAGGED, VerificationStatus.REJECTED))
        failed += sum(1 for f in financials if f.validation_status in (
            FinancialValidationStatus.AMOUNT_MISMATCH,
            FinancialValidationStatus.DUPLICATE_DOCUMENT,
            FinancialValidationStatus.SUSPICIOUS_REPEATED,
        ))

        # Duplicates
        ev_hashes = [e.file_hash_sha256 for e in evidences if e.file_hash_sha256]
        hash_counts: Dict[str, int] = {}
        for h in ev_hashes:
            hash_counts[h] = hash_counts.get(h, 0) + 1
        dup_ev = sum(1 for c in hash_counts.values() if c > 1)

        inv_counts: Dict[str, int] = {}
        for f in financials:
            if f.invoice_number:
                norm_inv = f.invoice_number.strip().upper()
                inv_counts[norm_inv] = inv_counts.get(norm_inv, 0) + 1
        dup_inv = sum(1 for c in inv_counts.values() if c > 1)
        duplicates = dup_ev + dup_inv

        revisions = sum(1 for e in evidences if e.supersedes_id is not None)
        # Superseded items are those referenced by supersedes_id
        superseded_ids = {str(e.supersedes_id) for e in evidences if e.supersedes_id is not None}
        superseded_count = sum(1 for e in evidences if str(e.id) in superseded_ids)

        return SubmissionAttemptSummary(
            total_submissions=total,
            verified_count=verified,
            failed_count=failed,
            duplicate_count=duplicates,
            revisions_count=revisions,
            superseded_count=superseded_count,
        )


# Global default instance
default_integrity_service = IntegrityService()


def get_integrity_service() -> IntegrityService:
    """Return default IntegrityService singleton."""
    return default_integrity_service
