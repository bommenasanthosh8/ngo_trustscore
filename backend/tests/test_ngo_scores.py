"""
Tests for NGO Transparency Score Engine:
- Aggregation of historical project verification performance across entire portfolio
- Multi-factor configurable scoring (evidence scores, financial value weighting, verification status, audit history, disputes, historical performance)
- Rejection of simplistic 'verified/total' calculation in favor of financial-value-weighted multi-factor model
- Strict terminology requirement: "Evidence-based transparency/verification indicator." (NEVER "Probability that NGO is honest.")
- Explainable bulleted explanation generation
- Snapshot persistence and history retrieval: GET /ngos/{id}/score and GET /ngos/{id}/score/history
- Configurable weights override verification
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuditDecisionType, ProjectStatus, UserRole
from app.models.ngo import NGO
from app.models.project import Project
from app.models.score import ScoreSnapshot
from app.models.user import User
from app.scores.ngo_engine import (
    NGOTransparencyScoreEngine,
    NGOTransparencyScoreWeights,
    OFFICIAL_INDICATOR_DESCRIPTION,
)


async def register_user(client: AsyncClient, role: str = "NGO", org_name: str = None):
    """Helper to register and login a user with given role."""
    email = f"{role.lower()}_{uuid.uuid4().hex[:6]}@platform.org"
    reg_payload = {
        "email": email,
        "password": "Password123!",
        "full_name": f"Test {role.capitalize()}",
        "role": role,
    }
    if role == "NGO":
        reg_payload["organization_name"] = org_name or f"Transparency Trust {uuid.uuid4().hex[:4]}"
        reg_payload["registration_number"] = f"NGO-TRANS-{uuid.uuid4().hex[:6].upper()}"

    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()["data"]
    user_id = uuid.UUID(me_data["id"])
    ngo_id = uuid.UUID(me_data["ngo_id"]) if me_data.get("ngo_id") else None

    return user_id, ngo_id, email, headers


async def create_test_project(client: AsyncClient, ngo_headers: dict, **kwargs) -> dict:
    """Helper to create a project with geographic location."""
    default_payload = {
        "name": kwargs.get("name", "Rural Clinic Expansion"),
        "category": kwargs.get("category", "HEALTHCARE"),
        "description": "Healthcare facility infrastructure and equipment expansion.",
        "target_amount": kwargs.get("budget", 500000.0),
        "expected_beneficiaries": 800,
        "expected_outcome": "Improved rural health services.",
        "location": {
            "location_name": "Chennai, Tamil Nadu, India",
            "latitude": 13.0827,
            "longitude": 80.2707,
            "gps_accuracy": 5.0,
            "geofence_radius": 200.0,
        },
    }
    res = await client.post("/api/v1/projects", json=default_payload, headers=ngo_headers)
    assert res.status_code == 201
    return res.json()["data"]


@pytest.mark.asyncio
async def test_cold_start_ngo_score(client: AsyncClient, db_session: AsyncSession):
    """
    Test score calculation for a newly registered NGO with 0 projects.
    Verifies graceful fallback, correct terminology, explainable bullets, and snapshot creation.
    """
    user_id, ngo_id, email, ngo_headers = await register_user(client, "NGO", "Cold Start Foundation")
    assert ngo_id is not None

    # Call GET /ngos/{id}/score
    score_res = await client.get(f"/api/v1/ngos/{ngo_id}/score")
    assert score_res.status_code == 200
    data = score_res.json()["data"]

    # Verify required return fields
    assert "final_score" in data
    assert data["project_count"] == 0
    assert data["verified_count"] == 0
    assert data["partially_verified_count"] == 0
    assert data["pending_count"] == 0
    assert data["disputed_count"] == 0
    assert "weighted_evidence_quality" in data
    assert "audit_performance" in data
    assert "historical_trend" in data
    assert isinstance(data["explanation"], list)
    assert len(data["explanation"]) >= 3

    # CRITICAL TERMINOLOGY CHECK
    assert data["indicator_description"] == OFFICIAL_INDICATOR_DESCRIPTION
    raw_response_text = score_res.text
    assert "Probability that NGO is honest" not in raw_response_text
    assert "probability that ngo is honest" not in raw_response_text.lower()

    # Verify ScoreSnapshot recorded in DB
    snap_stmt = select(ScoreSnapshot).where(
        ScoreSnapshot.ngo_id == ngo_id,
        ScoreSnapshot.project_id.is_(None),
    )
    snap_res = await db_session.execute(snap_stmt)
    snapshot = snap_res.scalar_one_or_none()
    assert snapshot is not None
    assert float(snapshot.composite_score) == pytest.approx(data["final_score"], 0.1)


@pytest.mark.asyncio
async def test_multi_project_value_weighted_score(client: AsyncClient, db_session: AsyncSession):
    """
    Test scoring across multiple projects with different financial values and verification statuses.
    Verifies that the score is NOT simply (verified / total).
    A high-value verified project should dominate the weighted score over a smaller pending project.
    """
    user_id, ngo_id, email, ngo_headers = await register_user(client, "NGO", "Multi Project Society")
    assert ngo_id is not None

    # Project 1: High value (1,000,000) - mark as VERIFIED with high evidence score
    p1 = await create_test_project(client, ngo_headers, name="Mega Hospital Wing", budget=1000000.0)
    # Project 2: Low value (100,000) - mark as PENDING with low evidence score
    p2 = await create_test_project(client, ngo_headers, name="Village Notice Board", budget=100000.0)

    # Directly set statuses and evidence scores in database
    p1_obj = await db_session.get(Project, uuid.UUID(p1["id"]))
    p1_obj.status = ProjectStatus.VERIFIED
    p1_obj.evidence_score = 90.0

    p2_obj = await db_session.get(Project, uuid.UUID(p2["id"]))
    p2_obj.status = ProjectStatus.UNDER_VERIFICATION
    p2_obj.evidence_score = 40.0

    await db_session.commit()

    # Call GET /ngos/{id}/score
    score_res = await client.get(f"/api/v1/ngos/{ngo_id}/score")
    assert score_res.status_code == 200
    data = score_res.json()["data"]

    assert data["project_count"] == 2
    assert data["verified_count"] == 1
    assert data["partially_verified_count"] == 0
    assert data["pending_count"] == 1
    assert data["disputed_count"] == 0

    # Simple ratio would be 1 / 2 = 50%, but financial value of verified is 1,000,000 / 1,100,000 = ~90.9%
    # Weighted evidence quality is (1,000,000 * 90 + 100,000 * 40) / 1,100,000 = ~85.45
    assert data["weighted_evidence_quality"] > 80.0
    # Final score must be well above 50 (simplistic 50% verified projects)
    assert data["final_score"] > 75.0

    # Check narrative explanation
    bullet_texts = " ".join(data["explanation"])
    assert "% of project value supported by verified evidence" in bullet_texts
    assert "evidence across" in bullet_texts.lower()


@pytest.mark.asyncio
async def test_audit_and_dispute_penalties(client: AsyncClient, db_session: AsyncSession):
    """
    Test that active disputes and negative audit decisions appropriately reduce
    the transparency indicator and show clear explanations.
    """
    from app.models.audit import Audit, AuditDecision
    from app.models.dispute import Dispute
    from app.models.enums import AuditStatus, DisputeStatus

    user_id, ngo_id, email, ngo_headers = await register_user(client, "NGO", "Dispute Impact Foundation")
    assert ngo_id is not None

    # Create 2 projects
    p1 = await create_test_project(client, ngo_headers, name="Water Facility A", budget=200000.0)
    p2 = await create_test_project(client, ngo_headers, name="Water Facility B", budget=200000.0)

    p1_obj = await db_session.get(Project, uuid.UUID(p1["id"]))
    p1_obj.status = ProjectStatus.DISPUTED
    p1_obj.evidence_score = 55.0

    p2_obj = await db_session.get(Project, uuid.UUID(p2["id"]))
    p2_obj.status = ProjectStatus.UNDER_VERIFICATION
    p2_obj.evidence_score = 60.0

    # Add an active dispute on Project 1
    dispute = Dispute(
        project_id=p1_obj.id,
        raised_by_id=user_id,
        reason="Challenging negative audit assessment on pipeline depth.",
        status=DisputeStatus.OPEN,
    )
    db_session.add(dispute)

    # Add an audit on Project 1 with DISCREPANCY decision
    audit = Audit(
        project_id=p1_obj.id,
        auditor_id=user_id,
        selection_reason="HIGH_RISK",
        status=AuditStatus.CONCLUDED,
    )
    db_session.add(audit)
    await db_session.flush()

    decision = AuditDecision(
        audit_id=audit.id,
        decided_by_id=user_id,
        decision=AuditDecisionType.DISCREPANCY,
        findings="Pipe depth found to be less than contracted depth.",
    )
    db_session.add(decision)
    await db_session.commit()

    # Call GET /ngos/{id}/score
    score_res = await client.get(f"/api/v1/ngos/{ngo_id}/score")
    assert score_res.status_code == 200
    data = score_res.json()["data"]

    assert data["disputed_count"] == 1
    # Check factors
    dispute_factor = data["factors"]["dispute_impact"]
    assert dispute_factor["raw_score"] < 70.0
    audit_factor = data["factors"]["audit_performance"]
    assert audit_factor["raw_score"] < 50.0

    # Explanation bullets should reflect active dispute
    bullet_texts = " ".join(data["explanation"])
    assert "dispute" in bullet_texts.lower()


@pytest.mark.asyncio
async def test_score_history_snapshots(client: AsyncClient, db_session: AsyncSession):
    """
    Test GET /ngos/{id}/score/history retrieves chronological score snapshots.
    """
    user_id, ngo_id, email, ngo_headers = await register_user(client, "NGO", "Historical NGO")
    assert ngo_id is not None

    # Compute score twice to generate snapshots
    res1 = await client.get(f"/api/v1/ngos/{ngo_id}/score")
    assert res1.status_code == 200

    res2 = await client.get(f"/api/v1/ngos/{ngo_id}/score")
    assert res2.status_code == 200

    # Retrieve history
    hist_res = await client.get(f"/api/v1/ngos/{ngo_id}/score/history")
    assert hist_res.status_code == 200
    history = hist_res.json()["data"]

    assert isinstance(history, list)
    assert len(history) >= 2
    first = history[0]
    assert "id" in first
    assert "composite_score" in first
    assert "breakdown" in first
    assert "calculated_at" in first
    assert str(first["ngo_id"]) == str(ngo_id)


@pytest.mark.asyncio
async def test_configurable_weights_override(db_session: AsyncSession):
    """
    Test that the scoring algorithm is fully configurable and not hard-coded.
    Custom weights alter the calculation as expected.
    """
    clean_ngo = NGO(
        name=f"Weight Test NGO {uuid.uuid4().hex[:6]}",
        registration_number=f"NGO-WEIGHTS-{uuid.uuid4().hex[:6].upper()}",
        contact_email="weights@platform.org",
    )
    db_session.add(clean_ngo)
    await db_session.commit()

    engine = NGOTransparencyScoreEngine()

    # Configuration 1: 100% weight on evidence quality
    weights_eq_only = NGOTransparencyScoreWeights(
        evidence_quality=1.0,
        value_verification=0.0,
        audit_performance=0.0,
        dispute_impact=0.0,
        historical_trend=0.0,
    )
    score1 = await engine.calculate_score(
        db_session, clean_ngo, weights_override=weights_eq_only, record_snapshot=False
    )

    # Configuration 2: 100% weight on dispute impact (which starts at 100 for clean NGO)
    weights_dispute_only = NGOTransparencyScoreWeights(
        evidence_quality=0.0,
        value_verification=0.0,
        audit_performance=0.0,
        dispute_impact=1.0,
        historical_trend=0.0,
    )
    score2 = await engine.calculate_score(
        db_session, clean_ngo, weights_override=weights_dispute_only, record_snapshot=False
    )

    # Under dispute-only weighting with zero disputes, score is 100
    assert score2.final_score == 100.0
    # Under evidence-only with zero projects, score is baseline 50
    assert score1.final_score == 50.0
    # Scores must differ due to configurable weights
    assert score1.final_score != score2.final_score



@pytest.mark.asyncio
async def test_scores_router_alias_endpoints(client: AsyncClient, db_session: AsyncSession):
    """
    Test that the alias endpoints /scores/ngos/{id} and /scores/ngos/{id}/snapshots work cleanly.
    """
    user_id, ngo_id, email, ngo_headers = await register_user(client, "NGO", "Alias NGO")
    assert ngo_id is not None

    res = await client.get(f"/api/v1/scores/ngos/{ngo_id}")
    assert res.status_code == 200
    assert res.json()["data"]["ngo_id"] == str(ngo_id)

    res_snaps = await client.get(f"/api/v1/scores/ngos/{ngo_id}/snapshots")
    assert res_snaps.status_code == 200
    assert isinstance(res_snaps.json()["data"], list)
