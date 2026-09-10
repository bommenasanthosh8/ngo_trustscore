from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional
import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.ngo import NGO
    from app.models.project import Project
    from app.models.evidence import Evidence
    from app.models.financial_evidence import FinancialEvidence
    from app.models.audit import Audit
    from app.models.dispute import Dispute


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(nullable=False, default=UserRole.DONOR, index=True)

    # Foreign key to NGO if user belongs to an NGO
    ngo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ngos.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    ngo: Mapped[Optional["NGO"]] = relationship("NGO", back_populates="users", foreign_keys=[ngo_id])
    created_projects: Mapped[List["Project"]] = relationship("Project", back_populates="created_by")
    submitted_evidences: Mapped[List["Evidence"]] = relationship("Evidence", back_populates="submitted_by")
    submitted_financial_evidences: Mapped[List["FinancialEvidence"]] = relationship("FinancialEvidence", back_populates="submitted_by")
    audits_assigned: Mapped[List["Audit"]] = relationship("Audit", back_populates="auditor", foreign_keys="[Audit.auditor_id]")
    disputes_raised: Mapped[List["Dispute"]] = relationship("Dispute", back_populates="raised_by")

    __table_args__ = (
        Index("ix_users_role_ngo_id", "role", "ngo_id"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
