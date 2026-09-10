from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
import uuid

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.project import Project
    from app.models.score import ScoreSnapshot


from app.models.enums import NGOVerificationStatus


class NGO(BaseModel):
    __tablename__ = "ngos"

    name: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    registration_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    darpan_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    authorized_representative: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Prototype verification status handled by ADMIN
    verification_status: Mapped[NGOVerificationStatus] = mapped_column(
        nullable=False,
        default=NGOVerificationStatus.PENDING,
        index=True,
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="ngo", foreign_keys="User.ngo_id")
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="ngo", cascade="all, delete-orphan")
    score_snapshots: Mapped[List["ScoreSnapshot"]] = relationship("ScoreSnapshot", back_populates="ngo")

    def __repr__(self) -> str:
        return f"<NGO id={self.id} name={self.name!r} reg={self.registration_number}>"
