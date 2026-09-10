from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import EvidenceType, LocationStatus, VerificationStatus

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User
    from app.models.verification import VerificationResult


def _get_evidence_location_type():
    try:
        from app.core.config import get_settings
        if "sqlite" in get_settings().DATABASE_URL:
            return Text
    except Exception:
        pass
    return Geometry(geometry_type="POINT", srid=4326, spatial_index=True)


class Evidence(BaseModel):
    __tablename__ = "evidences"

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

    evidence_type: Mapped[EvidenceType] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # File & storage details
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False, default="")  # Local path or storage reference
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False, default="file")
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="application/octet-stream")
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Timestamps (explicit separation between capture time and upload time)
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # GPS coordinates & accuracy
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_status: Mapped[LocationStatus] = mapped_column(
        nullable=False,
        default=LocationStatus.LOCATION_UNAVAILABLE,
    )

    # PostGIS Location from GPS coordinates (SRID 4326) / SQLite fallback
    location: Mapped[Optional[object]] = mapped_column(
        _get_evidence_location_type(),
        nullable=True,
    )

    # Structured metadata summary (EXIF details, camera model, invoice data, notes)
    metadata_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Immutability & correction revision reference
    supersedes_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidences.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    verification_status: Mapped[VerificationStatus] = mapped_column(
        nullable=False,
        default=VerificationStatus.PENDING,
        index=True,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="evidences")
    submitted_by: Mapped["User"] = relationship("User", back_populates="submitted_evidences")
    verification_results: Mapped[List["VerificationResult"]] = relationship(
        "VerificationResult",
        back_populates="evidence",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Evidence id={self.id} title={self.title!r} type={self.evidence_type} status={self.verification_status}>"
