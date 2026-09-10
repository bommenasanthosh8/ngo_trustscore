"""
Evidence Verification Engine.

Orchestrates independent verification checks across 10 dimensions:
1. LocationCheck
2. TimestampCheck
3. TimelineCheck
4. DuplicateMediaCheck
5. ImageSimilarityCheck
6. MetadataCheck
7. OCRCheck
8. FinancialConsistencyCheck
9. ProjectIdentityCheck
10. EvidenceCompletenessCheck

Computes weighted overall evidence quality, aggregates risk flags,
determines recommended actions (NO_ADDITIONAL_ACTION, MANUAL_REVIEW, AUDIT_RECOMMENDED),
and persists audit verification results without directly accusing the NGO of fraud.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.enums import (
    ProjectStatus,
    RecommendedAction,
    VerificationStatus,
)
from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence
from app.models.project import Project
from app.models.verification import VerificationResult
from app.schemas.verification import CheckResultSchema, VerificationReportResponse
from app.verification.checks.base import BaseVerificationCheck, CheckResult
from app.verification.checks.location import LocationCheck
from app.verification.checks.timestamp import TimestampCheck
from app.verification.checks.timeline import TimelineCheck
from app.verification.checks.duplicate import DuplicateMediaCheck
from app.verification.checks.similarity import ImageSimilarityCheck
from app.verification.checks.metadata import MetadataCheck
from app.verification.checks.ocr import OCRCheck
from app.verification.checks.financial import FinancialConsistencyCheck
from app.verification.checks.project_identity import ProjectIdentityCheck
from app.verification.checks.completeness import EvidenceCompletenessCheck

logger = logging.getLogger(__name__)

# Check weights for calculating overall evidence quality score
CHECK_WEIGHTS: Dict[str, float] = {
    "LocationCheck": 1.2,
    "TimestampCheck": 1.0,
    "TimelineCheck": 1.0,
    "DuplicateMediaCheck": 1.5,
    "ImageSimilarityCheck": 0.8,
    "MetadataCheck": 0.8,
    "OCRCheck": 1.0,
    "FinancialConsistencyCheck": 1.5,
    "ProjectIdentityCheck": 1.2,
    "EvidenceCompletenessCheck": 1.0,
}

CRITICAL_AUDIT_FLAGS = {
    "CROSS_PROJECT_MEDIA_REUSE",
    "DUPLICATE_DOCUMENT",
    "SUSPICIOUS_REPEATED",
    "OCR_FOREIGN_PROJECT_ID_DETECTED",
    "BEFORE_COMPLETION_IDENTICAL_PHOTO",
    "EVIDENCE_FOREIGN_PROJECT_RELATION",
    "UNAUTHORIZED_EVIDENCE_UPLOADER",
}


class VerificationEngine:
    """
    Central engine orchestrating the 10 independent verification checks.
    """

    def __init__(self, checks: Optional[List[BaseVerificationCheck]] = None) -> None:
        self.checks: List[BaseVerificationCheck] = checks or [
            LocationCheck(),
            TimestampCheck(),
            TimelineCheck(),
            DuplicateMediaCheck(),
            ImageSimilarityCheck(),
            MetadataCheck(),
            OCRCheck(),
            FinancialConsistencyCheck(),
            ProjectIdentityCheck(),
            EvidenceCompletenessCheck(),
        ]

    async def verify_project(
        self,
        db: AsyncSession,
        project: Project,
        target_evidence_id: Optional[uuid.UUID] = None,
    ) -> VerificationReportResponse:
        """
        Run the complete 10-point verification check suite for a project.
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

        target_evidence: Optional[Evidence] = None
        if target_evidence_id:
            target_evidence = next((e for e in evidences if e.id == target_evidence_id), None)

        # 3. Execute all independent checks
        check_results: List[CheckResult] = []
        all_risk_flags: set[str] = set()
        total_weighted_score = 0.0
        total_weights = 0.0
        missing_evidence: List[str] = []

        for check in self.checks:
            try:
                res = await check.evaluate(
                    db=db,
                    project=project,
                    evidences=evidences,
                    financials=financials,
                    target_evidence=target_evidence,
                )
            except Exception as exc:
                logger.error(f"Error evaluating check {check.name}: {exc}", exc_info=True)
                res = CheckResult(
                    check_name=check.name,
                    status="ERROR",
                    score=50.0,
                    explanation=f"Check encountered an execution issue: {str(exc)}",
                    risk_flags=["CHECK_EXECUTION_ERROR"],
                    details={"error": str(exc)},
                )

            check_results.append(res)
            all_risk_flags.update(res.risk_flags)

            weight = CHECK_WEIGHTS.get(res.check_name, 1.0)
            total_weighted_score += res.score * weight
            total_weights += weight

            # Extract missing evidence details if reported by completeness
            if res.check_name == "EvidenceCompletenessCheck":
                missing_evidence = res.details.get("missing_stages", [])

        # 4. Calculate overall evidence quality score [0 - 100]
        overall_score = round(total_weighted_score / total_weights, 2) if total_weights > 0 else 0.0

        # Determine overall quality
        if overall_score >= 80.0:
            overall_quality = "HIGH_QUALITY"
        elif overall_score >= 50.0:
            overall_quality = "MEDIUM_QUALITY"
        else:
            overall_quality = "LOW_QUALITY"

        # 5. Determine Recommended Action
        # (NO_ADDITIONAL_ACTION, MANUAL_REVIEW, AUDIT_RECOMMENDED)
        # Never label NGO directly as fraudulent.
        has_critical_flags = any(flag in CRITICAL_AUDIT_FLAGS for flag in all_risk_flags)

        if has_critical_flags or overall_score < 50.0:
            recommended_action = RecommendedAction.AUDIT_RECOMMENDED
        elif overall_score < 80.0 or len(all_risk_flags) > 0:
            recommended_action = RecommendedAction.MANUAL_REVIEW
        else:
            recommended_action = RecommendedAction.NO_ADDITIONAL_ACTION

        now_utc = datetime.now(timezone.utc)

        # 6. Persist verification records
        project.evidence_score = overall_score
        project.evidence_score_updated_at = now_utc

        # Update project status only if currently UNDER_VERIFICATION, EVIDENCE_COLLECTION, or CREATED
        if project.status in (ProjectStatus.UNDER_VERIFICATION, ProjectStatus.EVIDENCE_COLLECTION, ProjectStatus.CREATED):
            if overall_score >= 80.0 and recommended_action == RecommendedAction.NO_ADDITIONAL_ACTION:
                project.status = ProjectStatus.VERIFIED
            elif overall_score >= 50.0:
                project.status = ProjectStatus.PARTIALLY_VERIFIED
            else:
                project.status = ProjectStatus.UNDER_VERIFICATION

        # If evaluating a specific target evidence, persist its VerificationResult record
        if target_evidence:
            v_res = VerificationResult(
                evidence_id=target_evidence.id,
                geofence_match=next(
                    (c.status in ("MATCH", "NEAR") for c in check_results if c.check_name == "LocationCheck"),
                    None,
                ),
                geofence_distance_meters=next(
                    (c.details.get("distance_meters") for c in check_results if c.check_name == "LocationCheck"),
                    None,
                ),
                timestamp_valid=next(
                    (c.status == "VALID" for c in check_results if c.check_name == "TimestampCheck"),
                    True,
                ),
                tampering_detected=bool(has_critical_flags),
                ai_confidence_score=overall_score,
                raw_details={
                    "overall_quality": overall_quality,
                    "recommended_action": recommended_action.value,
                    "risk_flags": sorted(list(all_risk_flags)),
                    "check_results": [c.to_dict() for c in check_results],
                },
                verified_at=now_utc,
            )
            db.add(v_res)
            target_evidence.verification_status = (
                VerificationStatus.VERIFIED if overall_score >= 80.0 else VerificationStatus.FLAGGED
            )

        await db.commit()

        # Build standardized API response
        serialized_checks = [
            CheckResultSchema(
                check_name=c.check_name,
                status=c.status,
                score=c.score,
                explanation=c.explanation,
                risk_flags=c.risk_flags,
                details=c.details,
            )
            for c in check_results
        ]

        return VerificationReportResponse(
            project_id=project.id,
            project_code=project.project_code,
            overall_score=overall_score,
            overall_quality=overall_quality,
            recommended_action=recommended_action,
            risk_flags=sorted(list(all_risk_flags)),
            missing_evidence=missing_evidence,
            individual_checks=serialized_checks,
            evaluated_at=now_utc,
            evidence_count=len(evidences),
            financial_evidence_count=len(financials),
            target_evidence_id=target_evidence_id,
        )


# Global default engine instance
default_verification_engine = VerificationEngine()


def get_verification_engine() -> VerificationEngine:
    """Return default VerificationEngine instance."""
    return default_verification_engine
