"""
TimelineCheck — Verifies project milestone progression:
- Permanent projects: BEFORE -> PROGRESS -> COMPLETION (sequence & presence)
- One-time events: EVENT
- Distribution: EVENT + appropriate confirmation (FINANCIAL or OTHER)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProjectType, VerificationModel
from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence
from app.models.project import Project
from app.verification.checks.base import BaseVerificationCheck, CheckResult


class TimelineCheck(BaseVerificationCheck):
    @property
    def name(self) -> str:
        return "TimelineCheck"

    async def evaluate(
        self,
        db: AsyncSession,
        project: Project,
        evidences: List[Evidence],
        financials: List[FinancialEvidence],
        target_evidence: Optional[Evidence] = None,
    ) -> CheckResult:
        model = project.verification_model or VerificationModel.PERMANENT
        category = project.project_type

        # Group evidences by type
        by_type: Dict[str, List[Evidence]] = {}
        for e in evidences:
            t = e.evidence_type.value
            by_type.setdefault(t, []).append(e)

        risk_flags: List[str] = []
        score = 100.0

        is_permanent = (
            model == VerificationModel.PERMANENT or
            category in (ProjectType.INFRASTRUCTURE, ProjectType.WATER_AND_SANITATION, ProjectType.SANITATION)
        )
        is_distribution = category in (ProjectType.FOOD_DISTRIBUTION, ProjectType.RELIEF_DISTRIBUTION)
        is_event = model == VerificationModel.ONE_TIME_EVENT or category in (ProjectType.EDUCATION, ProjectType.HEALTHCARE)

        if is_permanent:
            # Check presence of BEFORE, PROGRESS, COMPLETION
            if "BEFORE" not in by_type:
                risk_flags.append("MISSING_BEFORE_STAGE")
                score -= 25.0
            if "PROGRESS" not in by_type:
                risk_flags.append("MISSING_PROGRESS_STAGE")
                score -= 20.0
            if "COMPLETION" not in by_type:
                risk_flags.append("MISSING_COMPLETION_STAGE")
                score -= 25.0

            # Check chronological sequence if stages are present
            if "BEFORE" in by_type and "COMPLETION" in by_type:
                earliest_before = min((e.captured_at or e.uploaded_at) for e in by_type["BEFORE"])
                latest_completion = max((e.captured_at or e.uploaded_at) for e in by_type["COMPLETION"])
                if earliest_before > latest_completion:
                    risk_flags.append("TIMELINE_SEQUENCE_INVALID")
                    score -= 40.0

        elif is_distribution:
            # Distribution requires EVENT + supporting confirmation (FINANCIAL or OTHER)
            if "EVENT" not in by_type:
                risk_flags.append("MISSING_EVENT_EVIDENCE")
                score -= 40.0
            if not financials and "FINANCIAL" not in by_type and "OTHER" not in by_type:
                risk_flags.append("MISSING_DISTRIBUTION_CONFIRMATION")
                score -= 30.0

        elif is_event:
            if "EVENT" not in by_type:
                risk_flags.append("MISSING_EVENT_EVIDENCE")
                score -= 40.0

        score = max(0.0, score)
        status = "PASSED" if not risk_flags else ("WARNING" if score >= 60.0 else "FAILED")

        explanation = (
            f"Timeline milestones fully satisfy requirements for {category.value} ({model.value})."
            if not risk_flags
            else f"Timeline validation flagged: {', '.join(risk_flags)}."
        )

        return CheckResult(
            check_name=self.name,
            status=status,
            score=score,
            explanation=explanation,
            risk_flags=risk_flags,
            details={
                "verification_model": model.value,
                "project_category": category.value,
                "milestone_counts": {k: len(v) for k, v in by_type.items()},
            },
        )
