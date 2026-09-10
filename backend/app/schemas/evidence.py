from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EvidenceType, LocationStatus, VerificationStatus


class EvidenceUploadMetadata(BaseModel):
    """Metadata passed alongside file upload."""
    title: str = Field(..., min_length=2, max_length=255)
    evidence_type: EvidenceType
    description: Optional[str] = None
    captured_at: Optional[datetime] = None
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    gps_accuracy: Optional[float] = Field(None, ge=0.0)
    supersedes_id: Optional[uuid.UUID] = None
    metadata_summary: Optional[Dict[str, Any]] = None


class UploaderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    submitted_by_id: uuid.UUID
    uploader: Optional[UploaderSummary] = None

    evidence_type: EvidenceType
    title: str
    description: Optional[str] = None

    storage_key: str
    original_filename: str
    mime_type: str
    file_size: int
    file_hash_sha256: str

    captured_at: Optional[datetime] = None
    uploaded_at: datetime
    created_at: datetime

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_accuracy: Optional[float] = None
    location_status: LocationStatus

    metadata_summary: Optional[Dict[str, Any]] = None
    supersedes_id: Optional[uuid.UUID] = None
    verification_status: VerificationStatus


class EvidenceListResponse(BaseModel):
    items: List[EvidenceResponse]
    total: int
    project_id: uuid.UUID


class EvidenceTimelineItem(BaseModel):
    id: uuid.UUID
    title: str
    evidence_type: EvidenceType
    description: Optional[str] = None
    original_filename: str
    file_hash_sha256: str
    captured_at: Optional[datetime] = None
    uploaded_at: datetime
    effective_timestamp: datetime  # captured_at or uploaded_at for chronological ordering
    location_status: LocationStatus
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_accuracy: Optional[float] = None
    verification_status: VerificationStatus
    supersedes_id: Optional[uuid.UUID] = None
    is_revision: bool = False
    uploader_name: Optional[str] = None


class EvidenceTimelineResponse(BaseModel):
    project_id: uuid.UUID
    project_title: str
    timeline: List[EvidenceTimelineItem]
    milestone_summary: Dict[str, int]
    total_items: int
