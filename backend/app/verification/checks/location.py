"""
LocationCheck — Compares project registered coordinates against evidence coordinates
using geodetic distance calculation. Never compares against NGO office location.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LocationStatus
from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence
from app.models.project import Project
from app.verification.checks.base import BaseVerificationCheck, CheckResult


def calculate_geodetic_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Great Circle distance in meters between two lat/lon pairs on WGS-84."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class LocationCheck(BaseVerificationCheck):
    @property
    def name(self) -> str:
        return "LocationCheck"

    async def evaluate(
        self,
        db: AsyncSession,
        project: Project,
        evidences: List[Evidence],
        financials: List[FinancialEvidence],
        target_evidence: Optional[Evidence] = None,
    ) -> CheckResult:
        geofence_radius = float(project.geofence_radius or 500.0)

        # If evaluating a specific evidence item
        eval_items = [target_evidence] if target_evidence else evidences

        if not eval_items:
            return CheckResult(
                check_name=self.name,
                status="UNAVAILABLE",
                score=50.0,
                explanation="No evidence items available to evaluate location.",
                details={"geofence_radius": geofence_radius, "distance_meters": None},
            )

        # Check if project has site coordinates registered
        if project.latitude is None or project.longitude is None:
            return CheckResult(
                check_name=self.name,
                status="UNAVAILABLE",
                score=50.0,
                explanation="Project site does not have registered coordinates for spatial verification.",
                details={"geofence_radius": geofence_radius, "distance_meters": None},
            )

        # Filter items with captured GPS
        gps_items = [
            e for e in eval_items
            if e.location_status == LocationStatus.CAPTURED and e.latitude is not None and e.longitude is not None
        ]

        if not gps_items:
            return CheckResult(
                check_name=self.name,
                status="UNAVAILABLE",
                score=50.0,
                explanation="GPS coordinates unavailable on submitted evidence. GPS is only one verification signal.",
                details={"geofence_radius": geofence_radius, "distance_meters": None},
            )

        # Evaluate distances
        distances = []
        for e in gps_items:
            d = calculate_geodetic_distance(
                float(project.latitude),
                float(project.longitude),
                float(e.latitude),  # type: ignore
                float(e.longitude),  # type: ignore
            )
            distances.append(d)

        avg_distance = sum(distances) / len(distances)
        max_distance = max(distances)

        details = {
            "geofence_radius": geofence_radius,
            "distance_meters": round(avg_distance, 1),
            "max_distance_meters": round(max_distance, 1),
            "gps_items_count": len(gps_items),
        }

        if avg_distance <= geofence_radius:
            return CheckResult(
                check_name=self.name,
                status="MATCH",
                score=100.0,
                explanation=f"Evidence coordinates match project site ({avg_distance:.1f}m within {geofence_radius:.0f}m geofence).",
                details=details,
            )
        elif avg_distance <= geofence_radius * 2.0:
            return CheckResult(
                check_name=self.name,
                status="NEAR",
                score=70.0,
                explanation=f"Evidence coordinates are near project site ({avg_distance:.1f}m, slightly beyond {geofence_radius:.0f}m geofence).",
                details=details,
            )
        else:
            return CheckResult(
                check_name=self.name,
                status="MISMATCH",
                score=20.0,
                explanation=f"Evidence coordinates are {avg_distance:.1f}m away from registered site ({geofence_radius:.0f}m radius).",
                risk_flags=["LOCATION_MISMATCH"],
                details=details,
            )
