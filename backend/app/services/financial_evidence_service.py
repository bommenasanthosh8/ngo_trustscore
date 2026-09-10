"""
Financial Evidence Service — Business logic for financial evidence collection,
deterministic OCR processing, duplicate & suspicious repeated document detection,
and comprehensive financial consistency evaluation.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User, UserRole
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.core.logging import audit_log
from app.models.activity import ActivityLog
from app.models.enums import (
    FinancialConsistencyStatus,
    FinancialDocumentType,
    FinancialValidationStatus,
    OCRStatus,
    ProjectStatus,
    VerificationStatus,
)
from app.models.financial_evidence import FinancialEvidence
from app.models.project import Project
from app.projects.service import get_project_by_id as resolve_project
from app.schemas.evidence import UploaderSummary
from app.schemas.financial_evidence import (
    FinancialConsistencyReport,
    FinancialEvidenceResponse,
    FinancialEvidenceUploadMetadata,
    ProjectFinancialEvidenceListResponse,
)
from app.services.ocr_service import get_ocr_engine
from app.storage.service import (
    generate_sha256,
    sanitize_filename,
    storage_service,
    validate_file,
)


def _build_uploader_summary(user: Optional[User]) -> Optional[UploaderSummary]:
    if not user:
        return None
    return UploaderSummary(
        id=user.id,
        email=user.email,
        full_name=user.full_name or user.email,
        role=user.role.value,
    )


def _serialize_financial_evidence(fe: FinancialEvidence) -> FinancialEvidenceResponse:
    uploader_sum = _build_uploader_summary(fe.submitted_by) if hasattr(fe, "submitted_by") else None

    return FinancialEvidenceResponse(
        id=fe.id,
        project_id=fe.project_id,
        submitted_by_id=fe.submitted_by_id,
        uploader=uploader_sum,
        document_type=fe.document_type,
        claimed_amount=float(fe.claimed_amount),
        extracted_amount=float(fe.extracted_amount) if fe.extracted_amount is not None else None,
        currency=fe.currency,
        document_date=fe.document_date,
        vendor_name=fe.vendor_name,
        description=fe.description,
        invoice_number=fe.invoice_number,
        storage_key=fe.storage_key,
        original_filename=fe.original_filename,
        mime_type=fe.mime_type,
        file_size=fe.file_size,
        document_hash=fe.document_hash,
        ocr_status=fe.ocr_status,
        ocr_engine=fe.ocr_engine,
        ocr_metadata=fe.ocr_metadata,
        validation_status=fe.validation_status,
        validation_flags=fe.validation_flags or [],
        verification_status=fe.verification_status,
        uploaded_at=fe.uploaded_at,
        created_at=fe.created_at,
    )


async def check_financial_access(
    project: Project,
    current_user: Optional[User] = None,
) -> None:
    """Access control for viewing project raw financial records and invoices."""
    if current_user is None:
        raise ForbiddenException("Raw financial documents and receipts are not accessible to unauthenticated visitors.")

    if current_user.role in (UserRole.ADMIN, UserRole.AUDITOR):
        return

    if current_user.role == UserRole.NGO:
        if current_user.ngo_id and project.ngo_id == current_user.ngo_id:
            return
        raise ForbiddenException("You do not have permission to view private financial documents for this project.")

    if current_user.role == UserRole.DONOR:
        raise ForbiddenException("Raw financial invoices and internal receipts are restricted to authorized auditors and the owning NGO.")

    raise ForbiddenException("Access to project financial records is restricted.")



async def upload_financial_evidence(
    db: AsyncSession,
    current_user: User,
    project_identifier: str | uuid.UUID,
    file: UploadFile,
    metadata: FinancialEvidenceUploadMetadata,
) -> FinancialEvidence:
    """
    Upload and process a financial evidence document.

    Enforces:
    1. Role authorization (only NGO owning the project or ADMIN can upload).
    2. File validation & safe storage key generation.
    3. SHA-256 hash generation.
    4. Duplicate & suspicious repeated document detection.
    5. OCR abstraction execution (extracting amount, vendor, invoice number).
    6. Amount mismatch detection (comparing claimed vs extracted).
    7. Audit logging.
    """
    # 1. Role Authorization
    if current_user.role not in (UserRole.NGO, UserRole.ADMIN):
        raise ForbiddenException("Only registered NGO representatives or administrators can submit financial evidence.")

    project = await resolve_project(db, project_identifier)

    # NGO Ownership Check
    if current_user.role == UserRole.NGO:
        if not current_user.ngo_id or project.ngo_id != current_user.ngo_id:
            raise ForbiddenException("You can only upload financial evidence for projects owned by your organization.")

    # 2. Read File Bytes & Validate
    content = await file.read()
    file_size = len(content)

    original_filename = file.filename or "financial_document"
    is_valid, err = validate_file(original_filename, file.content_type, file_size)
    if not is_valid:
        raise BadRequestException(err or "Invalid file upload.")

    # 3. Hash & Filename Sanitization
    document_hash = generate_sha256(content)
    sanitized_name = sanitize_filename(original_filename)
    fin_id = uuid.uuid4()

    # 4. Duplicate Document Detection
    flags: List[str] = []
    # Check if duplicate in the same project
    same_proj_res = await db.execute(
        select(FinancialEvidence).where(
            FinancialEvidence.project_id == project.id,
            FinancialEvidence.document_hash == document_hash,
        )
    )
    if same_proj_res.scalars().first():
        flags.append("DUPLICATE_DOCUMENT")

    # Check if suspicious repeat across any other project
    other_proj_res = await db.execute(
        select(FinancialEvidence).where(
            FinancialEvidence.project_id != project.id,
            FinancialEvidence.document_hash == document_hash,
        )
    )
    if other_proj_res.scalars().first():
        flags.append("SUSPICIOUS_REPEATED")

    # 5. Safe Storage
    now = datetime.now(timezone.utc)
    storage_key = f"financial/{project.id}/{now.strftime('%Y')}/{now.strftime('%m')}/{fin_id}_{sanitized_name}"
    saved_path = storage_service.save(storage_key, content)

    # 6. OCR Extraction via Service Abstraction
    ocr_engine = get_ocr_engine()
    ocr_res = await ocr_engine.extract(content, sanitized_name, file.content_type or "application/pdf")

    # 7. Validation Status & Amount Mismatch Check
    validation_status = FinancialValidationStatus.VALID
    if "DUPLICATE_DOCUMENT" in flags:
        validation_status = FinancialValidationStatus.DUPLICATE_DOCUMENT
    elif "SUSPICIOUS_REPEATED" in flags:
        validation_status = FinancialValidationStatus.SUSPICIOUS_REPEATED
    elif ocr_res.extracted_amount is not None:
        # Check tolerance (e.g. difference greater than 1.0 currency unit)
        diff = abs(metadata.claimed_amount - ocr_res.extracted_amount)
        if diff > 1.0:
            flags.append("AMOUNT_MISMATCH")
            validation_status = FinancialValidationStatus.AMOUNT_MISMATCH
        else:
            validation_status = FinancialValidationStatus.VALID
    else:
        validation_status = FinancialValidationStatus.PENDING

    # Merge OCR metadata with flags and details
    merged_metadata = dict(ocr_res.metadata)
    merged_metadata["detected_flags"] = flags

    fin_evidence = FinancialEvidence(
        id=fin_id,
        project_id=project.id,
        submitted_by_id=current_user.id,
        document_type=metadata.document_type,
        claimed_amount=metadata.claimed_amount,
        amount=metadata.claimed_amount,
        extracted_amount=ocr_res.extracted_amount,
        currency=metadata.currency,
        document_date=metadata.document_date or now,
        expense_date=metadata.document_date or now,
        vendor_name=metadata.vendor_name or ocr_res.extracted_vendor,
        description=metadata.description,
        invoice_number=metadata.invoice_number or ocr_res.extracted_invoice_number,
        storage_key=storage_key,
        document_path=saved_path,
        original_filename=sanitized_name,
        mime_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        document_hash=document_hash,
        ocr_status=ocr_res.status,
        ocr_engine=ocr_res.engine,
        ocr_raw_text=ocr_res.raw_text,
        ocr_metadata=merged_metadata,
        validation_status=validation_status,
        validation_flags=flags,
        verification_status=VerificationStatus.PENDING,
        uploaded_at=now,
    )

    db.add(fin_evidence)

    # 8. Audit Logging
    activity = ActivityLog(
        action="FINANCIAL_EVIDENCE_UPLOADED",
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        resource_type="financial_evidence",
        resource_id=str(fin_evidence.id),
        detail={
            "project_id": str(project.id),
            "project_code": project.project_code,
            "document_type": fin_evidence.document_type.value,
            "claimed_amount": fin_evidence.claimed_amount,
            "extracted_amount": fin_evidence.extracted_amount,
            "document_hash": document_hash,
            "flags": flags,
            "validation_status": validation_status.value,
            "ocr_engine": ocr_res.engine,
        },
        success=True,
    )
    db.add(activity)
    await db.flush()

    audit_log(
        action="FINANCIAL_EVIDENCE_UPLOADED",
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        resource_type="financial_evidence",
        resource_id=str(fin_evidence.id),
        detail={
            "project_id": str(project.id),
            "claimed_amount": fin_evidence.claimed_amount,
            "validation_status": validation_status.value,
            "flags": flags,
        },
    )

    return fin_evidence


def calculate_financial_consistency(
    project: Project,
    items: List[FinancialEvidence],
) -> FinancialConsistencyReport:
    """
    Compare:
    1. Project target amount
    2. Claimed expenditure
    3. Supported documented amount

    Calculates:
    - claimed_total
    - supported_total
    - difference
    - difference_percentage

    Flags:
    - MISSING_DOCUMENTS
    - AMOUNT_MISMATCH
    - DUPLICATE_DOCUMENT
    - SUSPICIOUS_REPEATED

    Returns consistency status:
    - CONSISTENT
    - MINOR_DISCREPANCY
    - MAJOR_DISCREPANCY
    - INSUFFICIENT_EVIDENCE
    (Does not automatically classify NGO as fraudulent).
    """
    target_amount = float(project.target_amount or project.total_budget or 0.0)

    if not items:
        return FinancialConsistencyReport(
            project_id=project.id,
            project_target_amount=target_amount,
            claimed_total=0.0,
            supported_total=0.0,
            difference=0.0,
            difference_percentage=0.0,
            status=FinancialConsistencyStatus.INSUFFICIENT_EVIDENCE,
            flags=["MISSING_DOCUMENTS"],
            items_count=0,
            summary_notes="No financial documentation has been submitted yet for this project.",
        )

    claimed_total = 0.0
    supported_total = 0.0
    aggregated_flags: set[str] = set()

    for item in items:
        claimed_amt = float(item.claimed_amount)
        claimed_total += claimed_amt

        # Collect item flags
        if item.validation_flags:
            for f in item.validation_flags:
                aggregated_flags.add(f)

        # Supported documented amount logic:
        # If document is duplicate or suspicious repeated, it cannot support expenditure
        if item.validation_status in (
            FinancialValidationStatus.DUPLICATE_DOCUMENT,
            FinancialValidationStatus.SUSPICIOUS_REPEATED,
        ):
            continue

        # If OCR extracted amount is present and valid, use extracted; else if valid claimed, use claimed
        if item.extracted_amount is not None:
            supported_total += float(item.extracted_amount)
        elif item.validation_status == FinancialValidationStatus.VALID or item.validation_status == FinancialValidationStatus.PENDING:
            supported_total += claimed_amt

    difference = abs(claimed_total - supported_total)
    difference_pct = (difference / claimed_total * 100.0) if claimed_total > 0.0 else 0.0

    # Determine status without accusing NGO of fraud
    flags_list = sorted(list(aggregated_flags))

    if supported_total == 0.0 and claimed_total > 0.0:
        status = FinancialConsistencyStatus.INSUFFICIENT_EVIDENCE
        notes = "Financial documents are under verification or lacking readable extraction."
    elif "DUPLICATE_DOCUMENT" in flags_list or "SUSPICIOUS_REPEATED" in flags_list or difference_pct > 10.0:
        status = FinancialConsistencyStatus.MAJOR_DISCREPANCY
        notes = (
            f"Significant expenditure variance detected ({difference_pct:.1f}% discrepancy). "
            f"Items flagged: {', '.join(flags_list) if flags_list else 'variance'}. Auditor review recommended."
        )
    elif difference_pct > 2.0 or "AMOUNT_MISMATCH" in flags_list:
        status = FinancialConsistencyStatus.MINOR_DISCREPANCY
        notes = (
            f"Minor difference between claimed and extracted totals ({difference_pct:.1f}% variance). "
            f"Likely tax/rounding or line-item adjustments."
        )
    else:
        status = FinancialConsistencyStatus.CONSISTENT
        notes = (
            f"Expenditures align with supported documentation within acceptable margins ({difference_pct:.1f}% variance)."
        )

    return FinancialConsistencyReport(
        project_id=project.id,
        project_target_amount=target_amount,
        claimed_total=round(claimed_total, 2),
        supported_total=round(supported_total, 2),
        difference=round(difference, 2),
        difference_percentage=round(difference_pct, 2),
        status=status,
        flags=flags_list,
        items_count=len(items),
        summary_notes=notes,
    )


async def get_project_financial_evidence(
    db: AsyncSession,
    current_user: User,
    project_identifier: str | uuid.UUID,
) -> ProjectFinancialEvidenceListResponse:
    """
    Retrieve all financial evidence records for a project along with
    the financial consistency evaluation report.
    """
    project = await resolve_project(db, project_identifier)
    await check_financial_access(project, current_user)

    query = (
        select(FinancialEvidence)
        .options(selectinload(FinancialEvidence.submitted_by))
        .where(FinancialEvidence.project_id == project.id)
        .order_by(FinancialEvidence.uploaded_at.desc())
    )
    result = await db.execute(query)
    items = result.scalars().all()

    report = calculate_financial_consistency(project, items)
    serialized_items = [_serialize_financial_evidence(it) for it in items]

    return ProjectFinancialEvidenceListResponse(
        project_id=project.id,
        items=serialized_items,
        consistency_report=report,
        total=len(serialized_items),
    )


async def get_financial_consistency_report(
    db: AsyncSession,
    current_user: Optional[User] = None,
    project_identifier: str | uuid.UUID = None,
) -> FinancialConsistencyReport:
    """Get standalone consistency report for a project."""
    project = await resolve_project(db, project_identifier)
    if not (project.is_publicly_visible and project.status != ProjectStatus.DISPUTED):
        await check_financial_access(project, current_user)

    query = (
        select(FinancialEvidence)
        .where(FinancialEvidence.project_id == project.id)
    )
    result = await db.execute(query)
    items = result.scalars().all()

    return calculate_financial_consistency(project, items)
