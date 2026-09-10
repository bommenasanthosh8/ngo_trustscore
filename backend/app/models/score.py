from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.ngo import NGO
    from app.models.project import Project


class ScoreSnapshot(BaseModel):
    __tablename__ = "score_snapshots"

    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    ngo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ngos.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    composite_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    breakdown: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="score_snapshots")
    ngo: Mapped[Optional["NGO"]] = relationship("NGO", back_populates="score_snapshots")

    __table_args__ = (
        CheckConstraint("composite_score >= 0 AND composite_score <= 100", name="chk_composite_score_range"),
        CheckConstraint("project_id IS NOT NULL OR ngo_id IS NOT NULL", name="chk_snapshot_has_target"),
    )

    def __repr__(self) -> str:
        return f"<ScoreSnapshot id={self.id} score={self.composite_score}>"
