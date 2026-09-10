"""
DuplicateMediaCheck:
- Uses SHA-256 hash to detect exact duplicate files within the project.
- Detects media reused across different projects (cross-project fraud/duplication signal).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence
from app.models.project import Project
from app.verification.checks.base import BaseVerificationCheck, CheckResult


class DuplicateMediaCheck(BaseVerificationCheck):
    @property
    def name(self) -> str:
        return "DuplicateMediaCheck"

    async def evaluate(
        self,
        db: AsyncSession,
        project: Project,
        evidences: List[Evidence],
        financials: List[FinancialEvidence],
        target_evidence: Optional[Evidence] = None,
    ) -> CheckResult:
        evidence_list = [target_evidence] if target_evidence else evidences
        if not evidence_list:
            return CheckResult(
                check_name=self.name,
                status="NO_DATA",
                score=100.0,
                explanation="No evidence items available to analyze for duplication.",
                risk_flags=[],
                details={"duplicate_count": 0, "cross_project_duplicates": []},
            )

        hashes = [e.file_hash_sha256 for e in evidence_list if e.file_hash_sha256]
        if not hashes:
            return CheckResult(
                check_name=self.name,
                status="NO_DATA",
                score=100.0,
                explanation="No valid hashes found on evidence items.",
                risk_flags=[],
                details={"duplicate_count": 0, "cross_project_duplicates": []},
            )

        # 1. Check for cross-project duplicate hashes in the database
        cross_query = select(Evidence).where(
            Evidence.file_hash_sha256.in_(hashes),
            Evidence.project_id != project.id,
        )
        cross_result = await db.execute(cross_query)
        cross_matches = cross_result.scalars().all()

        cross_project_flags = []
        if cross_matches:
            matched_pids = list({str(m.project_id) for m in cross_matches})
            cross_project_flags.append("CROSS_PROJECT_MEDIA_REUSE")
            return CheckResult(
                check_name=self.name,
                status="SUSPICIOUS",
                score=10.0,
                explanation=(
                    f"Evidence media hash matches files uploaded in {len(matched_pids)} other project(s) "
                    f"(Projects: {', '.join(matched_pids[:3])}). Potential media reuse across projects detected."
                ),
                risk_flags=cross_project_flags,
                details={
                    "cross_project_duplicate_count": len(cross_matches),
                    "matched_project_ids": matched_pids,
                    "matched_hashes": [m.file_hash_sha256 for m in cross_matches],
                },
            )

        # 2. Check for internal duplicate hashes within the same project
        # Count frequency of hashes
        hash_counts: Dict[str, int] = {}
        for h in hashes:
            hash_counts[h] = hash_counts.get(h, 0) + 1

        internal_dupes = {h: cnt for h, cnt in hash_counts.items() if cnt > 1}
        if internal_dupes:
            return CheckResult(
                check_name=self.name,
                status="INTERNAL_DUPLICATE",
                score=60.0,
                explanation=(
                    f"Detected {len(internal_dupes)} duplicate media file(s) uploaded within this project."
                ),
                risk_flags=["INTERNAL_DUPLICATE_MEDIA"],
                details={
                    "internal_duplicate_hashes": list(internal_dupes.keys()),
                    "duplicate_count": sum(internal_dupes.values()) - len(internal_dupes),
                },
            )

        return CheckResult(
            check_name=self.name,
            status="CLEAN",
            score=100.0,
            explanation="All media files have unique SHA-256 signatures with no cross-project reuse detected.",
            risk_flags=[],
            details={
                "duplicate_count": 0,
                "verified_hash_count": len(hashes),
            },
        )
