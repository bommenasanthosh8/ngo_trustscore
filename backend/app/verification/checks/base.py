"""
Base interface and dataclasses for independent verification checks.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence
from app.models.project import Project


@dataclass
class CheckResult:
    """Standardized output returned by every verification check."""
    check_name: str
    status: str
    score: float
    explanation: str
    risk_flags: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "status": self.status,
            "score": round(self.score, 2),
            "explanation": self.explanation,
            "risk_flags": self.risk_flags,
            "details": self.details,
        }


class BaseVerificationCheck(abc.ABC):
    """Abstract interface for all independent verification checks."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """The identifier of the check (e.g. LocationCheck)."""
        pass

    @abc.abstractmethod
    async def evaluate(
        self,
        db: AsyncSession,
        project: Project,
        evidences: List[Evidence],
        financials: List[FinancialEvidence],
        target_evidence: Optional[Evidence] = None,
    ) -> CheckResult:
        """Execute the verification check and return a standardized CheckResult."""
        pass
