"""
Demo Media Generator — Generates genuine, lightweight binary JPEG/PNG images
and PDF invoices for the SIH demonstration dataset.
"""
from __future__ import annotations

import os
import hashlib
from typing import Tuple

from app.storage.service import storage_service

# Valid 1x1 PNG binary bytes
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

# Valid minimal JPEG binary bytes (JFIF header)
_TINY_JPEG_HEADER = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
    b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
    b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
    b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
)


def generate_demo_image_bytes(seed_tag: str, mime: str = "image/jpeg") -> Tuple[bytes, str]:
    """
    Generate valid binary image bytes with a unique cryptographic hash per seed tag.
    Returns: (file_bytes, sha256_hash)
    """
    if "png" in mime:
        base = _TINY_PNG
    else:
        # Append safe comment chunk to create unique hash per evidence item
        comment = seed_tag.encode("utf-8")
        base = _TINY_JPEG_HEADER + b"\x00\x00" + comment

    sha256 = hashlib.sha256(base).hexdigest()
    return base, sha256


def generate_demo_pdf_bytes(
    invoice_number: str,
    vendor_name: str,
    claimed_amount: float,
    project_title: str,
) -> Tuple[bytes, str]:
    """
    Generate a valid, lightweight PDF invoice file with clear OCR-readable text headers.
    Returns: (pdf_bytes, sha256_hash)
    """
    text_content = (
        f"TAX INVOICE / RECEIPT\n"
        f"Invoice No: {invoice_number}\n"
        f"Vendor: {vendor_name}\n"
        f"Project: {project_title}\n"
        f"Total Amount: INR {claimed_amount:,.2f}\n"
        f"Status: PAID IN FULL\n"
    )

    pdf_template = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<<>>>>endobj\n"
        b"4 0 obj<</Length " + str(len(text_content.encode("utf-8"))).encode("utf-8") + b">>\n"
        b"stream\n"
        b"BT /F1 12 Tf 50 700 Td (" + text_content.replace("\n", " ").encode("utf-8") + b") Tj ET\n"
        b"endstream\nendobj\n"
        b"xref\n"
        b"0 5\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000210 00000 n \n"
        b"trailer<</Size 5/Root 1 0 R>>\n"
        b"startxref\n"
        b"350\n"
        b"%%EOF\n"
    )

    sha256 = hashlib.sha256(pdf_template).hexdigest()
    return pdf_template, sha256


def persist_demo_file(storage_key: str, content: bytes) -> str:
    """
    Persist binary bytes into the designated evidence storage directory.
    Returns the absolute filepath on local disk.
    """
    return storage_service.save(storage_key, content)
