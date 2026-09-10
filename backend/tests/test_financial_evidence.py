"""
Tests for Financial Evidence Module:
- Supported documents (invoice, bill, receipt, expense statement)
- Deterministic OCR service abstraction (extraction & mock disclaimer)
- Amount mismatch flagging (claimed vs extracted)
- Duplicate document detection within project
- Suspicious repeated document detection across projects
- Financial consistency calculation:
  - Target amount vs claimed vs supported
  - Difference & difference percentage
  - Statuses: CONSISTENT, MINOR_DISCREPANCY, MAJOR_DISCREPANCY, INSUFFICIENT_EVIDENCE
- Role authorization (NGO owner vs donor vs foreign NGO)
"""
import hashlib
import io
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient


async def create_test_project_with_ngo(client: AsyncClient, title: str = "Solar Borewell Project", budget: float = 500000.0):
    """Helper to register an NGO user and create a project."""
    ngo_email = f"fin_lead_{uuid.uuid4().hex[:6]}@finrelief.org"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": ngo_email,
            "password": "Password123!",
            "full_name": "Rajesh Mehra",
            "role": "NGO",
            "organization_name": f"Financial Relief Trust {uuid.uuid4().hex[:4]}",
            "registration_number": f"NGO-FIN-{uuid.uuid4().hex[:6].upper()}",
        },
    )
    assert reg_res.status_code == 201

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": ngo_email, "password": "Password123!"},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    proj_res = await client.post(
        "/api/v1/projects/",
        json={
            "title": title,
            "description": "Clean drinking water infrastructure",
            "project_type": "WATER_AND_SANITATION",
            "verification_model": "PERMANENT",
            "total_budget": budget,
            "target_amount": budget,
            "location": {
                "latitude": 26.9124,
                "longitude": 75.7873,
                "location_name": "Jaipur Rural Center",
                "geofence_radius": 500.0,
            },
        },
        headers=headers,
    )
    assert proj_res.status_code == 201
    return {
        "headers": headers,
        "ngo_email": ngo_email,
        "project_id": proj_res.json()["data"]["id"],
        "project_code": proj_res.json()["data"]["project_code"],
        "target_amount": budget,
    }


@pytest.mark.asyncio
async def test_upload_financial_evidence_with_ocr_extraction(client: AsyncClient):
    env = await create_test_project_with_ngo(client)
    project_id = env["project_id"]
    headers = env["headers"]

    # Simulated invoice file content containing plaintext extraction tokens
    invoice_content = (
        b"%PDF-1.4\n"
        b"Supplier: Supreme Hardware & Pumps Ltd\n"
        b"Invoice Number: INV-2026-7890\n"
        b"Date: 2026-08-15\n"
        b"Submersible Solar Pump 5HP: 45000.00\n"
        b"Grand Total: 45000.00 INR\n"
        b"%%EOF"
    )
    expected_hash = hashlib.sha256(invoice_content).hexdigest()

    files = {
        "file": ("pump_supplier_invoice.pdf", io.BytesIO(invoice_content), "application/pdf"),
    }
    data = {
        "claimed_amount": "45000.0",
        "document_type": "INVOICE",
        "currency": "INR",
        "vendor_name": "Supreme Hardware & Pumps Ltd",
        "invoice_number": "INV-2026-7890",
        "description": "5HP Solar Pump for Jaipur Well #1",
    }

    res = await client.post(
        f"/api/v1/projects/{project_id}/financial-evidence",
        files=files,
        data=data,
        headers=headers,
    )
    assert res.status_code == 201
    item = res.json()["data"]

    assert item["project_id"] == project_id
    assert float(item["claimed_amount"]) == 45000.0
    assert float(item["extracted_amount"]) == 45000.0
    assert item["document_type"] == "INVOICE"
    assert item["document_hash"] == expected_hash
    assert item["validation_status"] == "VALID"
    assert item["ocr_status"] == "COMPLETED"
    assert "mock_deterministic_adapter" in item["ocr_engine"]
    assert item["ocr_metadata"]["is_mock"] is True


@pytest.mark.asyncio
async def test_donor_forbidden_from_uploading_financial_evidence(client: AsyncClient, auth_headers):
    env = await create_test_project_with_ngo(client)
    project_id = env["project_id"]

    donor_id = uuid.uuid4()
    donor_headers = auth_headers(donor_id, role="DONOR", email="donor@test.com")

    files = {
        "file": ("receipt.pdf", io.BytesIO(b"dummy receipt"), "application/pdf"),
    }
    data = {
        "claimed_amount": "10000.0",
        "document_type": "RECEIPT",
    }

    res = await client.post(
        f"/api/v1/projects/{project_id}/financial-evidence",
        files=files,
        data=data,
        headers=donor_headers,
    )
    assert res.status_code == 403
    assert "Access denied" in res.json()["error"] or "Only registered NGO" in res.json()["error"]


@pytest.mark.asyncio
async def test_foreign_ngo_forbidden_from_uploading_financials(client: AsyncClient):
    env = await create_test_project_with_ngo(client)
    project_id = env["project_id"]

    # Second NGO
    ngo2_email = f"ngo2_{uuid.uuid4().hex[:6]}@other.org"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": ngo2_email,
            "password": "Password123!",
            "full_name": "Second Lead",
            "role": "NGO",
            "organization_name": "Second NGO",
            "registration_number": f"NGO-2-{uuid.uuid4().hex[:6].upper()}",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": ngo2_email, "password": "Password123!"},
    )
    ngo2_headers = {"Authorization": f"Bearer {login_res.json()['data']['access_token']}"}

    files = {
        "file": ("inv.pdf", io.BytesIO(b"content"), "application/pdf"),
    }
    data = {
        "claimed_amount": "5000.0",
        "document_type": "BILL",
    }

    res = await client.post(
        f"/api/v1/projects/{project_id}/financial-evidence",
        files=files,
        data=data,
        headers=ngo2_headers,
    )
    assert res.status_code == 403
    assert "projects owned by your organization" in res.json()["error"]


@pytest.mark.asyncio
async def test_amount_mismatch_flagged_by_ocr(client: AsyncClient):
    env = await create_test_project_with_ngo(client)
    project_id = env["project_id"]
    headers = env["headers"]

    # Document text says Grand Total: 20000, but NGO claims 35000
    doc_content = b"Item: Electric Cables\nGrand Total: 20000.00\nSupplier: WireCo"

    files = {
        "file": ("cables_bill.pdf", io.BytesIO(doc_content), "application/pdf"),
    }
    data = {
        "claimed_amount": "35000.0",  # Claiming 35,000 when doc says 20,000
        "document_type": "BILL",
    }

    res = await client.post(
        f"/api/v1/projects/{project_id}/financial-evidence",
        files=files,
        data=data,
        headers=headers,
    )
    assert res.status_code == 201
    item = res.json()["data"]

    assert float(item["claimed_amount"]) == 35000.0
    assert float(item["extracted_amount"]) == 20000.0
    assert item["validation_status"] == "AMOUNT_MISMATCH"
    assert "AMOUNT_MISMATCH" in item["validation_flags"]


@pytest.mark.asyncio
async def test_duplicate_document_detection_within_project(client: AsyncClient):
    env = await create_test_project_with_ngo(client)
    project_id = env["project_id"]
    headers = env["headers"]

    doc_content = b"Unique Receipt Bytes: XYZ-12345\nTotal: 15000.00"

    # First upload
    res1 = await client.post(
        f"/api/v1/projects/{project_id}/financial-evidence",
        files={"file": ("receipt_1.pdf", io.BytesIO(doc_content), "application/pdf")},
        data={"claimed_amount": "15000.0", "document_type": "RECEIPT"},
        headers=headers,
    )
    assert res1.status_code == 201
    assert "DUPLICATE_DOCUMENT" not in res1.json()["data"]["validation_flags"]

    # Second upload with identical bytes
    res2 = await client.post(
        f"/api/v1/projects/{project_id}/financial-evidence",
        files={"file": ("receipt_duplicate.pdf", io.BytesIO(doc_content), "application/pdf")},
        data={"claimed_amount": "15000.0", "document_type": "RECEIPT"},
        headers=headers,
    )
    assert res2.status_code == 201
    assert res2.json()["data"]["validation_status"] == "DUPLICATE_DOCUMENT"
    assert "DUPLICATE_DOCUMENT" in res2.json()["data"]["validation_flags"]


@pytest.mark.asyncio
async def test_suspicious_repeated_document_across_projects(client: AsyncClient):
    # Create Project 1 and upload document
    env1 = await create_test_project_with_ngo(client, title="Project One")
    shared_bytes = b"Shared Incurred Expense Slip #999\nTotal: 25000.00"

    res1 = await client.post(
        f"/api/v1/projects/{env1['project_id']}/financial-evidence",
        files={"file": ("slip.pdf", io.BytesIO(shared_bytes), "application/pdf")},
        data={"claimed_amount": "25000.0", "document_type": "EXPENSE_STATEMENT"},
        headers=env1["headers"],
    )
    assert res1.status_code == 201

    # Create Project 2 under same or different NGO and upload the EXACT same document
    env2 = await create_test_project_with_ngo(client, title="Project Two")
    res2 = await client.post(
        f"/api/v1/projects/{env2['project_id']}/financial-evidence",
        files={"file": ("slip_copy.pdf", io.BytesIO(shared_bytes), "application/pdf")},
        data={"claimed_amount": "25000.0", "document_type": "EXPENSE_STATEMENT"},
        headers=env2["headers"],
    )
    assert res2.status_code == 201
    assert res2.json()["data"]["validation_status"] == "SUSPICIOUS_REPEATED"
    assert "SUSPICIOUS_REPEATED" in res2.json()["data"]["validation_flags"]


@pytest.mark.asyncio
async def test_financial_consistency_evaluation_and_reports(client: AsyncClient):
    # 1. Project with 0 documents -> INSUFFICIENT_EVIDENCE
    env = await create_test_project_with_ngo(client, title="School Renovation", budget=200000.0)
    project_id = env["project_id"]
    headers = env["headers"]

    res_empty = await client.get(
        f"/api/v1/projects/{project_id}/financial-evidence/consistency",
        headers=headers,
    )
    assert res_empty.status_code == 200
    report_empty = res_empty.json()["data"]
    assert report_empty["status"] == "INSUFFICIENT_EVIDENCE"
    assert "MISSING_DOCUMENTS" in report_empty["flags"]

    # 2. Upload Document matching expenditure -> CONSISTENT
    doc1 = b"Invoice #1\nGrand Total: 50000.00"
    await client.post(
        f"/api/v1/projects/{project_id}/financial-evidence",
        files={"file": ("inv1.pdf", io.BytesIO(doc1), "application/pdf")},
        data={"claimed_amount": "50000.0", "document_type": "INVOICE"},
        headers=headers,
    )

    res_cons = await client.get(
        f"/api/v1/projects/{project_id}/financial-evidence",
        headers=headers,
    )
    assert res_cons.status_code == 200
    report_cons = res_cons.json()["data"]["consistency_report"]
    assert report_cons["status"] == "CONSISTENT"
    assert report_cons["claimed_total"] == 50000.0
    assert report_cons["supported_total"] == 50000.0
    assert report_cons["difference"] == 0.0
    assert report_cons["difference_percentage"] == 0.0

    # 3. Upload Document with major discrepancy -> MAJOR_DISCREPANCY
    # Claiming 50,000 but document only supports 10,000 (discrepancy > 10%)
    doc2 = b"Invoice #2\nGrand Total: 10000.00"
    await client.post(
        f"/api/v1/projects/{project_id}/financial-evidence",
        files={"file": ("inv2.pdf", io.BytesIO(doc2), "application/pdf")},
        data={"claimed_amount": "50000.0", "document_type": "INVOICE"},
        headers=headers,
    )

    res_major = await client.get(
        f"/api/v1/projects/{project_id}/financial-evidence/consistency",
        headers=headers,
    )
    assert res_major.status_code == 200
    report_major = res_major.json()["data"]
    # Total claimed: 100,000. Supported: 50,000 + 10,000 = 60,000. Diff = 40,000 (40%)
    assert report_major["status"] == "MAJOR_DISCREPANCY"
    assert report_major["difference_percentage"] > 10.0
    assert "AMOUNT_MISMATCH" in report_major["flags"]
