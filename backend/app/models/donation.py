from __future__ import annotations

from typing import TYPE_CHECKING, Optional
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import DonationStatus, PaymentMethod

if TYPE_CHECKING:
    from app.models.ngo import NGO
    from app.models.project import Project
    from app.models.user import User


class Donation(BaseModel):
    __tablename__ = "donations"

    donor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    donor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    donor_email: Mapped[str] = mapped_column(String(255), nullable=False)

    ngo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ngos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    payment_method: Mapped[PaymentMethod] = mapped_column(
        nullable=False, default=PaymentMethod.UPI
    )
    transaction_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    payment_status: Mapped[DonationStatus] = mapped_column(
        nullable=False, default=DonationStatus.SUCCESS, index=True
    )
    receipt_number: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    tax_exemption_eligible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    donor_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True
    )

    # Relationships
    donor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[donor_id])
    ngo: Mapped["NGO"] = relationship("NGO", foreign_keys=[ngo_id])
    project: Mapped[Optional["Project"]] = relationship("Project", foreign_keys=[project_id])

    def __repr__(self) -> str:
        return f"<Donation id={self.id} amount={self.amount} {self.currency} txn={self.transaction_id}>"
