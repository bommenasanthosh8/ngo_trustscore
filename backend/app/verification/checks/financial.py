"""
FinancialConsistencyCheck:
- Compares project target amount vs claimed expenditure vs supported documented amount.
- Calculates claimed_total, supported_total, difference, difference_percentage.
- Flags missing documents, amount mismatch, duplicate document, suspicious repeated document.
- Returns status: CONSISTENT, MINOR_DISCREPANCY, MAJOR_DISCREPANCY.
- Does NOT automatically classify NGO as fraudulent.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import FinancialConsistencyStatus
from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence
from app.models.project import Project
from app.services.financial_evidence_service import calculate_financial_consistency
from app.verification.checks.base import BaseVerificationCheck, CheckResult


class FinancialConsistencyCheck(BaseVerificationCheck):
    @property
    def name(self) -> str:
        return "FinancialConsistencyCheck"

    async def evaluate(
        self,
        db: AsyncSession,
        project: Project,
        evidences: List[Evidence],
        financials: List[FinancialEvidence],
        target_evidence: Optional[Evidence] = None,
    ) -> CheckResult:
        report = calculate_financial_consistency(project, financials)

        status_str = report.status.value

        # Calculate check score based on financial consistency
        if report.status == FinancialConsistencyStatus.CONSISTENT:
            score = 100.0
        elif report.status == FinancialConsistencyStatus.MINOR_DISCREPANCY:
            score = 75.0
        elif report.status == FinancialConsistencyStatus.MAJOR_DISCREPANCY:
            score = 30.0
        else:  # INSUFFICIENT_EVIDENCE
            score = 60.0

        return CheckResult(
            check_name=self.name,
            status=status_str,
            score=score,
            explanation=report.summary_notes,
            risk_flags=report.flags,
            details={
                "claimed_total": report.claimed_total,
                "supported_total": report.supported_total,
                "difference": report.difference,
                "difference_percentage": report.difference_percentage,
                "project_target_amount": report.project_target_amount,
                "items_count": report.items_count,
            },
        )
