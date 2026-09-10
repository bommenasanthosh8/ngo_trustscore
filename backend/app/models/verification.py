from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.evidence import Evidence
    from app.models.financial_evidence import FinancialEvidence


class VerificationResult(BaseModel):
    __tablename__ = "verification_results"

    evidence_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidences.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    financial_evidence_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_evidences.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    geofence_match: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    geofence_distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp_valid: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    tampering_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    raw_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    evidence: Mapped[Optional["Evidence"]] = relationship("Evidence", back_populates="verification_results")
    financial_evidence: Mapped[Optional["FinancialEvidence"]] = relationship("FinancialEvidence", back_populates="verification_results")

    __table_args__ = (
        CheckConstraint(
            "(evidence_id IS NOT NULL AND financial_evidence_id IS NULL) OR (evidence_id IS NULL AND financial_evidence_id IS NOT NULL)",
            name="chk_verification_result_target",
        ),
    )

    def __repr__(self) -> str:
        return f"<VerificationResult id={self.id} evidence={self.evidence_id} financial={self.financial_evidence_id}>"
