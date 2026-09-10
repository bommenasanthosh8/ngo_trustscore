from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional
import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import ProjectStatus, ProjectType, VerificationModel

if TYPE_CHECKING:
    from app.models.ngo import NGO
    from app.models.user import User
    from app.models.evidence import Evidence
    from app.models.financial_evidence import FinancialEvidence
    from app.models.risk import RiskAssessment
    from app.models.audit import Audit
    from app.models.score import ScoreSnapshot
    from app.models.dispute import Dispute


def _get_project_location_type():
    try:
        from app.core.config import get_settings
        if "sqlite" in get_settings().DATABASE_URL:
            return Text
    except Exception:
        pass
    return Geometry(geometry_type="POINT", srid=4326, spatial_index=True)


class Project(BaseModel):
    __tablename__ = "projects"

    ngo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ngos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    project_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: f"NGO-PRJ-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:6].upper()}",
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    project_type: Mapped[ProjectType] = mapped_column(nullable=False)
    verification_model: Mapped[VerificationModel] = mapped_column(nullable=False, default=VerificationModel.PERMANENT)
    status: Mapped[ProjectStatus] = mapped_column(
        nullable=False,
        default=ProjectStatus.CREATED,
        index=True,
    )

    # Location Details & Geofencing (Separate from NGO registered office)
    location_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geofence_radius: Mapped[float] = mapped_column(Float, default=500.0, nullable=False)
    gps_accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # PostGIS Location (SRID 4326) / SQLite fallback
    project_location: Mapped[Optional[object]] = mapped_column(
        _get_project_location_type(),
        nullable=True,
    )

    # Beneficiaries & Impact
    expected_beneficiaries: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expected_outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Financial details
    target_amount: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    total_budget: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    # Dates
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Server-side computed score
    evidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    evidence_score_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_publicly_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    ngo: Mapped["NGO"] = relationship("NGO", back_populates="projects")
    created_by: Mapped["User"] = relationship("User", back_populates="created_projects")
    evidences: Mapped[List["Evidence"]] = relationship("Evidence", back_populates="project", cascade="all, delete-orphan")
    financial_evidences: Mapped[List["FinancialEvidence"]] = relationship("FinancialEvidence", back_populates="project", cascade="all, delete-orphan")
    risk_assessments: Mapped[List["RiskAssessment"]] = relationship("RiskAssessment", back_populates="project", cascade="all, delete-orphan")
    audits: Mapped[List["Audit"]] = relationship("Audit", back_populates="project", cascade="all, delete-orphan")
    score_snapshots: Mapped[List["ScoreSnapshot"]] = relationship("ScoreSnapshot", back_populates="project", cascade="all, delete-orphan")
    disputes: Mapped[List["Dispute"]] = relationship("Dispute", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("total_budget IS NULL OR total_budget >= 0", name="chk_project_budget_positive"),
        CheckConstraint("evidence_score IS NULL OR (evidence_score >= 0 AND evidence_score <= 100)", name="chk_project_score_range"),
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} title={self.title!r} status={self.status}>"
