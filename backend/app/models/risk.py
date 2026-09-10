from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import RiskLevel

if TYPE_CHECKING:
    from app.models.project import Project


class RiskAssessment(BaseModel):
    __tablename__ = "risk_assessments"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    risk_level: Mapped[RiskLevel] = mapped_column(nullable=False, index=True)
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    factors: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="risk_assessments")

    __table_args__ = (
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="chk_risk_score_range"),
    )

    def __repr__(self) -> str:
        return f"<RiskAssessment id={self.id} project_id={self.project_id} level={self.risk_level} score={self.risk_score}>"
