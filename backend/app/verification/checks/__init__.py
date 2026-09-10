"""
Verification checks package: exports all 10 independent verification checks.
"""
from app.verification.checks.base import BaseVerificationCheck, CheckResult
from app.verification.checks.location import LocationCheck
from app.verification.checks.timestamp import TimestampCheck
from app.verification.checks.timeline import TimelineCheck
from app.verification.checks.duplicate import DuplicateMediaCheck
from app.verification.checks.similarity import ImageSimilarityCheck, ImageSimilarityAdapter
from app.verification.checks.metadata import MetadataCheck
from app.verification.checks.ocr import OCRCheck
from app.verification.checks.financial import FinancialConsistencyCheck
from app.verification.checks.project_identity import ProjectIdentityCheck
from app.verification.checks.completeness import EvidenceCompletenessCheck

__all__ = [
    "BaseVerificationCheck",
    "CheckResult",
    "LocationCheck",
    "TimestampCheck",
    "TimelineCheck",
    "DuplicateMediaCheck",
    "ImageSimilarityCheck",
    "ImageSimilarityAdapter",
    "MetadataCheck",
    "OCRCheck",
    "FinancialConsistencyCheck",
    "ProjectIdentityCheck",
    "EvidenceCompletenessCheck",
]
