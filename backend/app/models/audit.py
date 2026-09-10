from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import AuditDecisionType, AuditSelectionReason, AuditStatus

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class Audit(BaseModel):
    __tablename__ = "audits"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    auditor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    selection_reason: Mapped[AuditSelectionReason] = mapped_column(
        nullable=False,
        default=AuditSelectionReason.HIGH_RISK,
        index=True,
    )
    status: Mapped[AuditStatus] = mapped_column(
        nullable=False,
        default=AuditStatus.INITIATED,
        index=True,
    )
    scope: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    findings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="audits")
    auditor: Mapped["User"] = relationship("User", foreign_keys=[auditor_id], back_populates="audits_assigned")
    decisions: Mapped[List["AuditDecision"]] = relationship(
        "AuditDecision",
        foreign_keys="AuditDecision.audit_id",
        back_populates="audit",
        cascade="all, delete-orphan",
        order_by="AuditDecision.decided_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<Audit id={self.id} project_id={self.project_id} status={self.status}>"


class AuditDecision(BaseModel):
    __tablename__ = "audit_decisions"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[AuditDecisionType] = mapped_column(nullable=False, index=True)
    findings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supporting_evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    is_superseded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    superseded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audit_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    decided_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    audit: Mapped["Audit"] = relationship("Audit", foreign_keys=[audit_id], back_populates="decisions")
    decided_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[decided_by_id])

    def __repr__(self) -> str:
        return f"<AuditDecision id={self.id} audit_id={self.audit_id} decision={self.decision}>"
