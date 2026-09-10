"""
EvidenceCompletenessCheck:
- Determines whether all required evidence for the project category and lifecycle has been submitted.
- Pinpoints specific missing evidence stages (BEFORE, PROGRESS, COMPLETION, EVENT, FINANCIAL).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProjectType
from app.models.evidence import Evidence, EvidenceType
from app.models.financial_evidence import FinancialEvidence
from app.models.project import Project
from app.verification.checks.base import BaseVerificationCheck, CheckResult


class EvidenceCompletenessCheck(BaseVerificationCheck):
    @property
    def name(self) -> str:
        return "EvidenceCompletenessCheck"

    def get_category_requirements(self, category: ProjectType) -> List[str]:
        """Define stage requirements based on project category."""
        # Permanent infrastructure projects
        if category in (
            ProjectType.INFRASTRUCTURE,
            ProjectType.WATER_AND_SANITATION,
            ProjectType.SANITATION,
        ):
            return ["BEFORE", "PROGRESS", "COMPLETION", "FINANCIAL"]

        # Distribution and relief events
        if category in (
            ProjectType.FOOD_DISTRIBUTION,
            ProjectType.RELIEF_DISTRIBUTION,
        ):
            return ["EVENT", "FINANCIAL"]

        # Environmental & Agriculture
        if category in (
            ProjectType.ENVIRONMENT,
        ):
            return ["BEFORE", "COMPLETION", "FINANCIAL"]

        # Education, Health, or General
        return ["BEFORE", "COMPLETION", "FINANCIAL"]

    async def evaluate(
        self,
        db: AsyncSession,
        project: Project,
        evidences: List[Evidence],
        financials: List[FinancialEvidence],
        target_evidence: Optional[Evidence] = None,
    ) -> CheckResult:
        submitted_types: Set[str] = {e.evidence_type.value for e in evidences}
        if financials:
            submitted_types.add("FINANCIAL")

        category = project.project_type or ProjectType.OTHER
        required_stages = self.get_category_requirements(category)

        missing_stages = [req for req in required_stages if req not in submitted_types]

        total_req = len(required_stages)
        fulfilled_req = total_req - len(missing_stages)
        score = (fulfilled_req / total_req * 100.0) if total_req > 0 else 100.0

        risk_flags = []
        if missing_stages:
            if "COMPLETION" in missing_stages or "EVENT" in missing_stages:
                risk_flags.append("MISSING_OUTCOME_EVIDENCE")
            if "FINANCIAL" in missing_stages:
                risk_flags.append("MISSING_FINANCIAL_EVIDENCE")
            if "BEFORE" in missing_stages:
                risk_flags.append("MISSING_BASELINE_EVIDENCE")

        if not missing_stages:
            status = "COMPLETE"
            explanation = (
                f"All required evidence stages ({', '.join(required_stages)}) for category "
                f"'{category.value}' have been submitted."
            )
        elif fulfilled_req > 0:
            status = "PARTIAL"
            explanation = (
                f"Project has submitted {fulfilled_req}/{total_req} required evidence categories. "
                f"Missing stages: {', '.join(missing_stages)}."
            )
        else:
            status = "INCOMPLETE"
            explanation = (
                f"No required evidence stages submitted for category '{category.value}'. "
                f"Required: {', '.join(required_stages)}."
            )

        return CheckResult(
            check_name=self.name,
            status=status,
            score=round(score, 1),
            explanation=explanation,
            risk_flags=risk_flags,
            details={
                "project_category": category.value,
                "required_stages": required_stages,
                "submitted_stages": sorted(list(submitted_types)),
                "missing_stages": missing_stages,
                "completeness_ratio": f"{fulfilled_req}/{total_req}",
            },
        )
