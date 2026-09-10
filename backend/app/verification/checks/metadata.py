"""
MetadataCheck:
- Inspects EXIF metadata where available.
- Missing metadata is NOT automatically fraud (social media/chat apps strip EXIF).
- Statuses returned: AVAILABLE, MISSING, SUSPICIOUS.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence
from app.models.project import Project
from app.verification.checks.base import BaseVerificationCheck, CheckResult

# Known image manipulation tools
SUSPICIOUS_SOFTWARE_KEYWORDS = [
    "photoshop", "gimp", "canva", "picsart", "lightroom", "pixlr",
    "facetune", "snapseed", "aftershot", "affinity photo"
]


class MetadataCheck(BaseVerificationCheck):
    @property
    def name(self) -> str:
        return "MetadataCheck"

    async def evaluate(
        self,
        db: AsyncSession,
        project: Project,
        evidences: List[Evidence],
        financials: List[FinancialEvidence],
        target_evidence: Optional[Evidence] = None,
    ) -> CheckResult:
        items = [target_evidence] if target_evidence else evidences
        if not items:
            return CheckResult(
                check_name=self.name,
                status="MISSING",
                score=70.0,
                explanation="No evidence records available for metadata inspection.",
                risk_flags=[],
                details={"available_count": 0, "missing_count": 0, "suspicious_count": 0},
            )

        available_count = 0
        missing_count = 0
        suspicious_items = []

        for ev in items:
            meta = ev.metadata_summary or {}
            # An evidence has available metadata if it has make/model or dimensions or exif tags
            has_meta = bool(meta and (meta.get("make") or meta.get("model") or meta.get("camera") or meta.get("software") or meta.get("exif")))

            if not has_meta:
                missing_count += 1
                continue

            # Check for suspicious editing software
            software = str(meta.get("software", "")).lower()
            detected_software = [kw for kw in SUSPICIOUS_SOFTWARE_KEYWORDS if kw in software]

            # Check for suspicious dates in exif
            exif_date = meta.get("datetime") or meta.get("exif_date")
            is_suspicious_date = False
            if exif_date and isinstance(exif_date, str):
                if exif_date.startswith("1970") or exif_date.startswith("2099"):
                    is_suspicious_date = True

            if detected_software or is_suspicious_date:
                suspicious_items.append({
                    "evidence_id": str(ev.id),
                    "filename": ev.original_filename,
                    "software": software,
                    "reasons": detected_software + (["INVALID_EXIF_DATE"] if is_suspicious_date else []),
                })
            else:
                available_count += 1

        # Decision logic
        if suspicious_items:
            return CheckResult(
                check_name=self.name,
                status="SUSPICIOUS",
                score=35.0,
                explanation=(
                    f"{len(suspicious_items)} evidence item(s) contain metadata indicative of external photo editing "
                    f"or anomalous EXIF timestamps."
                ),
                risk_flags=["SUSPICIOUS_METADATA"],
                details={
                    "available_count": available_count,
                    "missing_count": missing_count,
                    "suspicious_count": len(suspicious_items),
                    "suspicious_items": suspicious_items,
                },
            )

        if available_count > 0:
            score = 100.0 if missing_count == 0 else 85.0
            return CheckResult(
                check_name=self.name,
                status="AVAILABLE",
                score=score,
                explanation=(
                    f"Valid camera/hardware metadata found on {available_count} item(s). "
                    f"({missing_count} item(s) lack metadata, which is normal for compressed or exported files)."
                ),
                risk_flags=[],
                details={
                    "available_count": available_count,
                    "missing_count": missing_count,
                    "suspicious_count": 0,
                },
            )

        # All missing - remember: "Missing metadata is NOT automatically fraud."
        return CheckResult(
            check_name=self.name,
            status="MISSING",
            score=70.0,
            explanation=(
                "EXIF metadata is absent across submitted evidence. Note: missing metadata is common "
                "when images are transferred through messaging apps (WhatsApp, Telegram) and is not evidence of fraud."
            ),
            risk_flags=["METADATA_ABSENT"],
            details={
                "available_count": 0,
                "missing_count": missing_count,
                "suspicious_count": 0,
            },
        )
