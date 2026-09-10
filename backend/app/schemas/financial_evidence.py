from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    FinancialConsistencyStatus,
    FinancialDocumentType,
    FinancialValidationStatus,
    OCRStatus,
    VerificationStatus,
)
from app.schemas.evidence import UploaderSummary


class FinancialEvidenceUploadMetadata(BaseModel):
    """Metadata passed alongside financial document upload."""
    claimed_amount: float = Field(..., gt=0.0, description="Amount claimed for expenditure")
    document_type: FinancialDocumentType = Field(default=FinancialDocumentType.INVOICE)
    currency: str = Field(default="INR", max_length=3)
    vendor_name: Optional[str] = Field(None, max_length=255)
    invoice_number: Optional[str] = Field(None, max_length=100)
    document_date: Optional[datetime] = None
    description: Optional[str] = None


class FinancialEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    submitted_by_id: uuid.UUID
    uploader: Optional[UploaderSummary] = None

    document_type: FinancialDocumentType
    claimed_amount: float
    extracted_amount: Optional[float] = None
    currency: str

    document_date: Optional[datetime] = None
    vendor_name: Optional[str] = None
    description: Optional[str] = None
    invoice_number: Optional[str] = None

    storage_key: str
    original_filename: str
    mime_type: str
    file_size: int
    document_hash: str

    ocr_status: OCRStatus
    ocr_engine: Optional[str] = None
    ocr_metadata: Optional[Dict[str, Any]] = None

    validation_status: FinancialValidationStatus
    validation_flags: Optional[List[str]] = None
    verification_status: VerificationStatus

    uploaded_at: datetime
    created_at: datetime


class FinancialConsistencyReport(BaseModel):
    project_id: uuid.UUID
    project_target_amount: float
    claimed_total: float
    supported_total: float
    difference: float
    difference_percentage: float
    status: FinancialConsistencyStatus
    flags: List[str]
    items_count: int
    summary_notes: str


class ProjectFinancialEvidenceListResponse(BaseModel):
    project_id: uuid.UUID
    items: List[FinancialEvidenceResponse]
    consistency_report: FinancialConsistencyReport
    total: int
