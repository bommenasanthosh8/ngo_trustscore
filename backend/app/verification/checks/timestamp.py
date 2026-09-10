"""
TimestampCheck — Verifies that evidence capture dates align with project start/completion dates
and detects suspiciously compressed timelines.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence
from app.models.project import Project
from app.verification.checks.base import BaseVerificationCheck, CheckResult


class TimestampCheck(BaseVerificationCheck):
    @property
    def name(self) -> str:
        return "TimestampCheck"

    async def evaluate(
        self,
        db: AsyncSession,
        project: Project,
        evidences: List[Evidence],
        financials: List[FinancialEvidence],
        target_evidence: Optional[Evidence] = None,
    ) -> CheckResult:
        eval_items = [target_evidence] if target_evidence else evidences

        if not eval_items:
            return CheckResult(
                check_name=self.name,
                status="UNAVAILABLE",
                score=50.0,
                explanation="No evidence items available to evaluate timestamps.",
            )

        risk_flags: List[str] = []
        dated_items: List[datetime] = []

        proj_start = project.start_date
        proj_end = project.end_date

        for ev in eval_items:
            t = ev.captured_at or ev.uploaded_at
            if t:
                # Ensure timezone-aware comparison
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                dated_items.append(t)

                if proj_start:
                    p_start = proj_start if proj_start.tzinfo else proj_start.replace(tzinfo=timezone.utc)
                    # Allow 2-day buffer for site pre-inspection
                    if t < p_start - timedelta(days=2):
                        if "EVIDENCE_PREDATES_PROJECT_START" not in risk_flags:
                            risk_flags.append("EVIDENCE_PREDATES_PROJECT_START")

                if proj_end:
                    p_end = proj_end if proj_end.tzinfo else proj_end.replace(tzinfo=timezone.utc)
                    # Allow 7-day grace period for final reporting
                    if t > p_end + timedelta(days=7):
                        if "EVIDENCE_AFTER_COMPLETION" not in risk_flags:
                            risk_flags.append("EVIDENCE_AFTER_COMPLETION")

        # Check for suspiciously compressed timeline
        # If there are items representing BEFORE, PROGRESS, COMPLETION within seconds/minutes
        if len(dated_items) >= 2:
            dated_items.sort()
            time_span = dated_items[-1] - dated_items[0]

            types_present = {e.evidence_type.value for e in eval_items}
            if {"BEFORE", "COMPLETION"}.issubset(types_present):
                # Multi-stage project compressed into less than 1 hour
                if time_span.total_seconds() < 3600:
                    risk_flags.append("COMPRESSED_TIMELINE")

        score = 100.0
        if "COMPRESSED_TIMELINE" in risk_flags:
            score -= 40.0
        if "EVIDENCE_PREDATES_PROJECT_START" in risk_flags:
            score -= 30.0
        if "EVIDENCE_AFTER_COMPLETION" in risk_flags:
            score -= 20.0

        score = max(10.0, score)
        status = "PASSED" if not risk_flags else ("WARNING" if score >= 60.0 else "FAILED")

        explanation = (
            "Evidence capture timestamps align with the project lifecycle."
            if not risk_flags
            else f"Timestamp anomalies detected: {', '.join(risk_flags)}."
        )

        return CheckResult(
            check_name=self.name,
            status=status,
            score=score,
            explanation=explanation,
            risk_flags=risk_flags,
            details={
                "project_start": proj_start.isoformat() if proj_start else None,
                "project_end": proj_end.isoformat() if proj_end else None,
                "dated_items_count": len(dated_items),
            },
        )
