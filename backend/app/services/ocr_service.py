"""
OCR Service Abstraction Layer.

Provides a pluggable OCR interface with a deterministic mock adapter
for environments lacking system OCR binaries (e.g., Tesseract or Google Cloud Vision).
Explicitly marks mock executions without falsely claiming real OCR engine origin.
"""
from __future__ import annotations

import abc
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from app.models.enums import OCRStatus


@dataclass
class OCROutput:
    """Standardized OCR extraction result."""
    status: OCRStatus
    engine: str
    is_mock: bool
    raw_text: Optional[str] = None
    extracted_amount: Optional[float] = None
    extracted_vendor: Optional[str] = None
    extracted_invoice_number: Optional[str] = None
    extracted_date: Optional[datetime] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseOCREngine(abc.ABC):
    """Abstract base class for OCR engines."""

    @property
    @abc.abstractmethod
    def engine_name(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def is_mock(self) -> bool:
        pass

    @abc.abstractmethod
    async def extract(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> OCROutput:
        """Extract text and financial fields from document bytes."""
        pass


class MockDeterministicOCREngine(BaseOCREngine):
    """
    Deterministic mock OCR adapter for development, prototyping, and CI testing.
    Uses regex rules on readable byte sequences and structured tokens.
    Never claims to be a neural/production OCR engine.
    """

    @property
    def engine_name(self) -> str:
        return "mock_deterministic_adapter_v1"

    @property
    def is_mock(self) -> bool:
        return True

    async def extract(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> OCROutput:
        if not file_bytes:
            return OCROutput(
                status=OCRStatus.FAILED,
                engine=self.engine_name,
                is_mock=True,
                confidence=0.0,
                metadata={"error": "Empty file content."},
            )

        # Attempt decoding readable ASCII/UTF-8 strings from document bytes
        extracted_text = ""
        try:
            # Decode ignoring errors to extract any plaintext substrings in PDFs/text
            extracted_text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            extracted_text = ""

        # Deterministic extraction logic
        found_amount: Optional[float] = None
        found_invoice_num: Optional[str] = None
        found_vendor: Optional[str] = None

        # 1. Look for explicit Total / Amount / Grand Total patterns
        amount_patterns = [
            r"(?:Total|Grand Total|Net Amount|Amount Paid|Invoice Amount|Total Amount|INR|Rs\.?)\s*[:=]?\s*(?:Rs\.?|INR)?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)",
            r"(?:claimed_amount|amount)\s*[:=]?\s*([0-9]+(?:\.[0-9]{1,2})?)",
        ]

        for pat in amount_patterns:
            match = re.search(pat, extracted_text, re.IGNORECASE)
            if match:
                clean_num_str = match.group(1).replace(",", "")
                try:
                    found_amount = float(clean_num_str)
                    break
                except ValueError:
                    pass

        # 2. Look for Invoice Number
        inv_match = re.search(
            r"(?:Invoice\s*(?:No|Number|#)?|Bill\s*No|Receipt\s*#)\s*[:=]?\s*([A-Za-z0-9\-_/]+)",
            extracted_text,
            re.IGNORECASE,
        )
        if inv_match:
            found_invoice_num = inv_match.group(1).strip()

        # 3. Look for Vendor Name pattern
        vendor_match = re.search(
            r"(?:Vendor|Supplier|Merchant|Paid To)\s*[:=]?\s*([A-Za-z0-9\s.,&'\-]+?)(?:\r|\n|$)",
            extracted_text,
            re.IGNORECASE,
        )
        if vendor_match:
            found_vendor = vendor_match.group(1).strip()

        # If nothing found in byte text, check if filename carries deterministic test hints
        # e.g., "invoice_50000_vendor.pdf" or "receipt_1250.jpg"
        if found_amount is None:
            fn_amount_match = re.search(r"(\d+(?:\.\d{2})?)", filename)
            if fn_amount_match and float(fn_amount_match.group(1)) > 100:
                found_amount = float(fn_amount_match.group(1))

        status = OCRStatus.COMPLETED if found_amount is not None or extracted_text.strip() else OCRStatus.SKIPPED
        confidence = 85.0 if found_amount is not None else 50.0

        metadata = {
            "engine": self.engine_name,
            "is_mock": True,
            "extraction_method": "deterministic_rule_based_mock",
            "disclaimer": "Simulated extraction via deterministic prototype adapter. No real external OCR service was invoked.",
            "file_size": len(file_bytes),
            "mime_type": mime_type,
            "matched_invoice_number": found_invoice_num,
            "matched_vendor": found_vendor,
        }

        # Truncate raw_text preview if large
        preview_text = extracted_text[:1000] if extracted_text else None

        return OCROutput(
            status=status,
            engine=self.engine_name,
            is_mock=True,
            raw_text=preview_text,
            extracted_amount=found_amount,
            extracted_vendor=found_vendor,
            extracted_invoice_number=found_invoice_num,
            confidence=confidence,
            metadata=metadata,
        )


# Global default OCR engine instance
default_ocr_engine: BaseOCREngine = MockDeterministicOCREngine()


def get_ocr_engine() -> BaseOCREngine:
    """Return the active OCR engine."""
    return default_ocr_engine
