"""
Project Pydantic schemas — request and response shapes for Project Management.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ProjectStatus, ProjectType, VerificationModel


# ── Location Data Structure ──────────────────────────────────────────────────
class ProjectLocationInput(BaseModel):
    """
    Geospatial location payload for project site.
    NGO selects on map, searches, or captures GPS — manual lat/long typing is not required.
    Note: The project location is independent of the NGO's registered office.
    """
    location_name: str = Field(..., min_length=2, max_length=500, description="Site location name / address")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude from map or device GPS")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude from map or device GPS")
    geofence_radius: float = Field(500.0, ge=10.0, le=50000.0, description="Geofence boundary radius in meters")
    gps_accuracy: Optional[float] = Field(None, ge=0.0, description="GPS device accuracy in meters when captured")
    selection_method: Optional[str] = Field("MAP_CLICK", description="MAP_CLICK | GPS_DEVICE | SEARCH_LOCATION")


class ProjectLocationResponse(BaseModel):
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geofence_radius: float = 500.0
    gps_accuracy: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


# ── Project Creation Request ──────────────────────────────────────────────────
class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=500, description="Official project name/title")
    category: ProjectType = Field(..., description="Project sector/category")
    description: Optional[str] = Field(None, max_length=10000, description="Detailed project description")
    target_amount: float = Field(100000.0, gt=0, description="Target funding / utilization budget amount")
    expected_beneficiaries: Optional[int] = Field(None, ge=0, description="Projected number of direct beneficiaries")
    start_date: Optional[datetime] = Field(None, description="Project start date")
    expected_completion_date: Optional[datetime] = Field(None, description="Expected completion date")
    location: Optional[ProjectLocationInput] = Field(None, description="Project site location with coordinates and geofence")
    expected_outcome: Optional[str] = Field(None, max_length=5000, description="Anticipated measurable impact and outcomes")
    verification_model: VerificationModel = Field(VerificationModel.PERMANENT, description="Verification model type")
    is_publicly_visible: bool = Field(True, description="Public transparency visibility toggle")
    is_sensitive: bool = Field(False, description="Sensitive project flag")

    # Optional alias support for title
    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, values: dict):
        if isinstance(values, dict):
            if "title" in values and "name" not in values:
                values["name"] = values["title"]
            if "total_budget" in values and "target_amount" not in values:
                values["target_amount"] = values["total_budget"]
            if "project_type" in values and "category" not in values:
                values["category"] = values["project_type"]
            if "end_date" in values and "expected_completion_date" not in values:
                values["expected_completion_date"] = values["end_date"]
            if "location" not in values and "latitude" in values and "longitude" in values:
                values["location"] = {
                    "location_name": values.get("location_name") or values.get("name") or "Project Site",
                    "latitude": values["latitude"],
                    "longitude": values["longitude"],
                }
        return values


# ── Project Update Request ────────────────────────────────────────────────────
class UpdateProjectRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=500)
    category: Optional[ProjectType] = None
    description: Optional[str] = Field(None, max_length=10000)
    target_amount: Optional[float] = Field(None, gt=0)
    expected_beneficiaries: Optional[int] = Field(None, ge=0)
    start_date: Optional[datetime] = None
    expected_completion_date: Optional[datetime] = None
    location: Optional[ProjectLocationInput] = None
    expected_outcome: Optional[str] = Field(None, max_length=5000)
    status: Optional[ProjectStatus] = Field(None, description="State transition request (strictly validated by backend)")

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, values: dict):
        if isinstance(values, dict):
            if "title" in values and "name" not in values:
                values["name"] = values["title"]
            if "total_budget" in values and "target_amount" not in values:
                values["target_amount"] = values["total_budget"]
            if "project_type" in values and "category" not in values:
                values["category"] = values["project_type"]
            if "end_date" in values and "expected_completion_date" not in values:
                values["expected_completion_date"] = values["end_date"]
        return values


# ── Project Detailed Response ─────────────────────────────────────────────────
class ProjectDetail(BaseModel):
    id: uuid.UUID
    project_code: str
    title: str
    category: ProjectType
    description: Optional[str] = None
    verification_model: VerificationModel
    status: ProjectStatus
    target_amount: Optional[float] = None
    total_budget: Optional[float] = None
    currency: str = "INR"
    expected_beneficiaries: Optional[int] = None
    expected_outcome: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geofence_radius: float = 500.0
    gps_accuracy: Optional[float] = None
    start_date: Optional[datetime] = None
    expected_completion_date: Optional[datetime] = None
    evidence_score: Optional[float] = None
    evidence_score_updated_at: Optional[datetime] = None
    ngo_id: uuid.UUID
    created_by_id: uuid.UUID
    is_publicly_visible: bool
    is_sensitive: bool = False
    approximate_latitude: Optional[float] = None
    approximate_longitude: Optional[float] = None
    ngo_name: Optional[str] = None
    risk_level: Optional[str] = "LOW"
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def map_project_attributes(cls, data):
        # Allow ORM models or dicts with project_type/title/end_date mapping
        if hasattr(data, "project_type") and not hasattr(data, "category"):
            # ORM instance
            category_val = getattr(data, "project_type")
            target_amt = getattr(data, "target_amount", None) or getattr(data, "total_budget", None)
            end_d = getattr(data, "end_date", None)
            lat = getattr(data, "latitude", None)
            lon = getattr(data, "longitude", None)
            approx_lat = round(lat, 2) if lat is not None else None
            approx_lon = round(lon, 2) if lon is not None else None

            # Check if category is sensitive or flagged
            is_sens = category_val in (ProjectType.RELIEF_DISTRIBUTION, ProjectType.HEALTHCARE) or getattr(data, "is_sensitive", False)

            # Resolve ngo_name safely without triggering lazy-load greenlet
            ngo_n = None
            if "ngo" in data.__dict__ and data.ngo:
                ngo_n = data.ngo.name

            # Resolve risk_level safely
            risk_l = "LOW"
            if "risk_assessments" in data.__dict__ and data.risk_assessments:
                risk_l = data.risk_assessments[-1].risk_level.value
            elif hasattr(data, "risk_level"):
                risk_l = getattr(data, "risk_level", "LOW")

            return {
                "id": data.id,
                "project_code": getattr(data, "project_code", f"NGO-PRJ-{str(data.id)[:8]}"),
                "title": data.title,
                "category": category_val,
                "description": data.description,
                "verification_model": data.verification_model,
                "status": data.status,
                "target_amount": target_amt,
                "total_budget": getattr(data, "total_budget", None),
                "currency": data.currency,
                "expected_beneficiaries": getattr(data, "expected_beneficiaries", None),
                "expected_outcome": getattr(data, "expected_outcome", None),
                "location_name": getattr(data, "location_name", None),
                "latitude": approx_lat if is_sens else lat,
                "longitude": approx_lon if is_sens else lon,
                "approximate_latitude": approx_lat,
                "approximate_longitude": approx_lon,
                "is_sensitive": is_sens,
                "ngo_name": ngo_n,
                "risk_level": risk_l,
                "geofence_radius": getattr(data, "geofence_radius", 500.0),
                "gps_accuracy": getattr(data, "gps_accuracy", None),
                "start_date": data.start_date,
                "expected_completion_date": end_d,
                "evidence_score": getattr(data, "evidence_score", None),
                "evidence_score_updated_at": getattr(data, "evidence_score_updated_at", None),
                "ngo_id": data.ngo_id,
                "created_by_id": data.created_by_id,
                "is_publicly_visible": data.is_publicly_visible,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        return data



# ── Project Summary Response ──────────────────────────────────────────────────
class ProjectSummary(BaseModel):
    id: uuid.UUID
    project_code: str
    title: str
    category: ProjectType
    verification_model: VerificationModel
    status: ProjectStatus
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geofence_radius: float = 500.0
    target_amount: Optional[float] = None
    currency: str = "INR"
    expected_beneficiaries: Optional[int] = None
    evidence_score: Optional[float] = None
    start_date: Optional[datetime] = None
    expected_completion_date: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def map_project_summary(cls, data):
        if hasattr(data, "project_type") and not hasattr(data, "category"):
            target_amt = getattr(data, "target_amount", None) or getattr(data, "total_budget", None)
            return {
                "id": data.id,
                "project_code": getattr(data, "project_code", f"NGO-PRJ-{str(data.id)[:8]}"),
                "title": data.title,
                "category": data.project_type,
                "verification_model": data.verification_model,
                "status": data.status,
                "location_name": getattr(data, "location_name", None),
                "latitude": getattr(data, "latitude", None),
                "longitude": getattr(data, "longitude", None),
                "geofence_radius": getattr(data, "geofence_radius", 500.0),
                "target_amount": target_amt,
                "currency": data.currency,
                "expected_beneficiaries": getattr(data, "expected_beneficiaries", None),
                "evidence_score": getattr(data, "evidence_score", None),
                "start_date": data.start_date,
                "expected_completion_date": getattr(data, "end_date", None),
                "created_at": data.created_at,
            }
        return data


# ── Location Search Result ────────────────────────────────────────────────────
class LocationSearchResult(BaseModel):
    location_name: str
    display_name: str
    latitude: float
    longitude: float
    state: Optional[str] = None
    country: str = "India"
