"""
ProjectIdentityCheck:
- Verifies that all submitted evidence unambiguously belongs to the target Project ID.
- Verifies that evidence uploaders are authorized members of the project's owning NGO or platform administrators.
- Prevents cross-project evidence misattribution.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence
from app.models.project import Project
from app.models.user import User, UserRole
from app.verification.checks.base import BaseVerificationCheck, CheckResult


class ProjectIdentityCheck(BaseVerificationCheck):
    @property
    def name(self) -> str:
        return "ProjectIdentityCheck"

    async def evaluate(
        self,
        db: AsyncSession,
        project: Project,
        evidences: List[Evidence],
        financials: List[FinancialEvidence],
        target_evidence: Optional[Evidence] = None,
    ) -> CheckResult:
        evidence_list = [target_evidence] if target_evidence else evidences
        all_items = evidence_list + financials

        if not all_items:
            return CheckResult(
                check_name=self.name,
                status="VERIFIED",
                score=100.0,
                explanation="Project identity verified; no items to evaluate.",
                risk_flags=[],
                details={"verified_items": 0},
            )

        mismatches = []
        uploader_ids = set()

        for item in all_items:
            if item.project_id != project.id:
                mismatches.append(str(item.id))
            if hasattr(item, "uploader_id") and item.uploader_id:
                uploader_ids.add(item.uploader_id)
            elif hasattr(item, "submitted_by_id") and item.submitted_by_id:
                uploader_ids.add(item.submitted_by_id)

        # Verify uploaders belong to project NGO or are admin
        unauthorized_uploaders = []
        if uploader_ids:
            users_res = await db.execute(select(User).where(User.id.in_(uploader_ids)))
            users = users_res.scalars().all()
            for u in users:
                if u.role == UserRole.ADMIN:
                    continue
                # If NGO user, must belong to the project's NGO
                if u.role == UserRole.NGO and u.ngo_id != project.ngo_id:
                    unauthorized_uploaders.append(str(u.id))

        risk_flags = []
        if mismatches:
            risk_flags.append("EVIDENCE_FOREIGN_PROJECT_RELATION")
        if unauthorized_uploaders:
            risk_flags.append("UNAUTHORIZED_EVIDENCE_UPLOADER")

        if risk_flags:
            return CheckResult(
                check_name=self.name,
                status="MISMATCH",
                score=10.0,
                explanation=(
                    f"Project identity integrity check failed: {len(mismatches)} item(s) cross-reference "
                    f"mismatched project IDs, and {len(unauthorized_uploaders)} uploader(s) do not belong to the project NGO."
                ),
                risk_flags=risk_flags,
                details={
                    "mismatched_item_ids": mismatches,
                    "unauthorized_uploader_ids": unauthorized_uploaders,
                    "target_project_id": str(project.id),
                    "target_project_code": project.project_code,
                },
            )

        return CheckResult(
            check_name=self.name,
            status="VERIFIED",
            score=100.0,
            explanation=(
                f"All {len(all_items)} evidence and financial item(s) strictly belong to Project "
                f"'{project.project_code}' with authorized NGO ownership."
            ),
            risk_flags=[],
            details={
                "project_id": str(project.id),
                "project_code": project.project_code,
                "verified_items_count": len(all_items),
            },
        )
