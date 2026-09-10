from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import (
    FinancialDocumentType,
    FinancialValidationStatus,
    OCRStatus,
    VerificationStatus,
)

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User
    from app.models.verification import VerificationResult


class FinancialEvidence(BaseModel):
    __tablename__ = "financial_evidences"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    submitted_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    document_type: Mapped[FinancialDocumentType] = mapped_column(
        nullable=False,
        default=FinancialDocumentType.INVOICE,
    )

    # Claimed amount & extracted amount
    claimed_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0.0)
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0.0)  # Kept for backward compatibility
    extracted_amount: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    # Document dates & metadata
    document_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expense_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    vendor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # File & storage details
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    document_path: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False, default="document")
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="application/octet-stream")
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # OCR Processing Fields
    ocr_status: Mapped[OCRStatus] = mapped_column(
        nullable=False,
        default=OCRStatus.PENDING,
    )
    ocr_engine: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ocr_raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Validation Status & Consistency Flags
    validation_status: Mapped[FinancialValidationStatus] = mapped_column(
        nullable=False,
        default=FinancialValidationStatus.PENDING,
    )
    validation_flags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # General Verification Status
    verification_status: Mapped[VerificationStatus] = mapped_column(
        nullable=False,
        default=VerificationStatus.PENDING,
        index=True,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="financial_evidences")
    submitted_by: Mapped["User"] = relationship("User", back_populates="submitted_financial_evidences")
    verification_results: Mapped[List["VerificationResult"]] = relationship(
        "VerificationResult",
        back_populates="financial_evidence",
        cascade="all, delete-orphan",
    )

    def __init__(self, **kwargs):
        if "amount" in kwargs and "claimed_amount" not in kwargs:
            kwargs["claimed_amount"] = kwargs["amount"]
        elif "claimed_amount" in kwargs and "amount" not in kwargs:
            kwargs["amount"] = kwargs["claimed_amount"]

        if "expense_date" in kwargs and "document_date" not in kwargs:
            kwargs["document_date"] = kwargs["expense_date"]
        elif "document_date" in kwargs and "expense_date" not in kwargs:
            kwargs["expense_date"] = kwargs["document_date"]

        if "document_path" in kwargs and "storage_key" not in kwargs:
            kwargs["storage_key"] = kwargs["document_path"]

        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return (
            f"<FinancialEvidence id={self.id} type={self.document_type} "
            f"claimed={self.claimed_amount} extracted={self.extracted_amount} status={self.validation_status}>"
        )
