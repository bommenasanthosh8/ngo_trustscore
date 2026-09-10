"""Initial Phase 1 schema — All core models with PostGIS support and strict constraints.

Revision ID: 0001
Revises: 
Create Date: 2026-09-08
"""
from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ── Enable PostGIS extension ───────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # ── ENUM types ────────────────────────────────────────────────────────────
    userrole = postgresql.ENUM("NGO", "DONOR", "AUDITOR", "ADMIN", name="userrole", create_type=True)
    userrole.create(op.get_bind())

    projecttype = postgresql.ENUM(
        "INFRASTRUCTURE", "EDUCATION", "FOOD_DISTRIBUTION",
        "HEALTHCARE", "SANITATION", "ENVIRONMENT", "RELIEF_DISTRIBUTION",
        name="projecttype", create_type=True,
    )
    projecttype.create(op.get_bind())

    projectstatus = postgresql.ENUM("DRAFT", "ACTIVE", "COMPLETED", "SUSPENDED", name="projectstatus", create_type=True)
    projectstatus.create(op.get_bind())

    verificationmodel = postgresql.ENUM("PERMANENT", "ONE_TIME_EVENT", "FINANCIAL_ASSISTANCE", name="verificationmodel", create_type=True)
    verificationmodel.create(op.get_bind())

    evidencetype = postgresql.ENUM("IMAGE", "VIDEO", "DOCUMENT", "INSPECTION_REPORT", name="evidencetype", create_type=True)
    evidencetype.create(op.get_bind())

    verificationstatus = postgresql.ENUM("PENDING", "VERIFIED", "FLAGGED", "REJECTED", name="verificationstatus", create_type=True)
    verificationstatus.create(op.get_bind())

    risklevel = postgresql.ENUM("LOW", "MEDIUM", "HIGH", "CRITICAL", name="risklevel", create_type=True)
    risklevel.create(op.get_bind())

    auditstatus = postgresql.ENUM("INITIATED", "IN_PROGRESS", "CONCLUDED", "DISPUTED", name="auditstatus", create_type=True)
    auditstatus.create(op.get_bind())

    auditdecisiontype = postgresql.ENUM("APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED", "FLAGGED_FRAUD", name="auditdecisiontype", create_type=True)
    auditdecisiontype.create(op.get_bind())

    disputestatus = postgresql.ENUM("OPEN", "UNDER_REVIEW", "RESOLVED", "DISMISSED", name="disputestatus", create_type=True)
    disputestatus.create(op.get_bind())

    # ── 1. ngos ───────────────────────────────────────────────────────────────
    op.create_table(
        "ngos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("registration_number", sa.String(100), nullable=False),
        sa.Column("darpan_id", sa.String(100), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("contact_email", sa.String(320), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ngos_name", "ngos", ["name"], unique=True)
    op.create_index("ix_ngos_registration_number", "ngos", ["registration_number"], unique=True)
    op.create_index("ix_ngos_darpan_id", "ngos", ["darpan_id"], unique=True)

    # ── 2. users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("NGO", "DONOR", "AUDITOR", "ADMIN", name="userrole"), nullable=False, server_default="DONOR"),
        sa.Column("ngo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ngos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_ngo_id", "users", ["ngo_id"])
    op.create_index("ix_users_role_ngo_id", "users", ["role", "ngo_id"])

    # ── 3. projects ───────────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("ngo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ngos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("project_type", sa.Enum(name="projecttype"), nullable=False),
        sa.Column("verification_model", sa.Enum(name="verificationmodel"), nullable=False),
        sa.Column("status", sa.Enum(name="projectstatus"), nullable=False, server_default="DRAFT"),
        sa.Column("project_location", geoalchemy2.Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True),
        sa.Column("location_name", sa.String(500), nullable=True),
        sa.Column("total_budget", sa.Numeric(15, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("evidence_score_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_publicly_visible", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("total_budget IS NULL OR total_budget >= 0", name="chk_project_budget_positive"),
        sa.CheckConstraint("evidence_score IS NULL OR (evidence_score >= 0 AND evidence_score <= 100)", name="chk_project_score_range"),
    )
    op.create_index("ix_projects_ngo_id", "projects", ["ngo_id"])
    op.create_index("ix_projects_created_by_id", "projects", ["created_by_id"])
    op.create_index("ix_projects_status", "projects", ["status"])

    # ── 4. evidences ──────────────────────────────────────────────────────────
    op.create_table(
        "evidences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submitted_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("evidence_type", sa.Enum(name="evidencetype"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("file_hash_sha256", sa.String(64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", geoalchemy2.Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True),
        sa.Column("verification_status", sa.Enum(name="verificationstatus"), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evidences_project_id", "evidences", ["project_id"])
    op.create_index("ix_evidences_submitted_by_id", "evidences", ["submitted_by_id"])
    op.create_index("ix_evidences_file_hash_sha256", "evidences", ["file_hash_sha256"])
    op.create_index("ix_evidences_verification_status", "evidences", ["verification_status"])

    # ── 5. financial_evidences ────────────────────────────────────────────────
    op.create_table(
        "financial_evidences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submitted_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("invoice_number", sa.String(100), nullable=True),
        sa.Column("vendor_name", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("expense_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_path", sa.String(1000), nullable=False),
        sa.Column("document_hash", sa.String(64), nullable=False),
        sa.Column("verification_status", sa.Enum(name="verificationstatus"), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="chk_financial_evidence_amount_positive"),
    )
    op.create_index("ix_financial_evidences_project_id", "financial_evidences", ["project_id"])
    op.create_index("ix_financial_evidences_submitted_by_id", "financial_evidences", ["submitted_by_id"])
    op.create_index("ix_financial_evidences_invoice_number", "financial_evidences", ["invoice_number"])
    op.create_index("ix_financial_evidences_document_hash", "financial_evidences", ["document_hash"])
    op.create_index("ix_financial_evidences_verification_status", "financial_evidences", ["verification_status"])

    # ── 6. verification_results ───────────────────────────────────────────────
    op.create_table(
        "verification_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evidences.id", ondelete="CASCADE"), nullable=True),
        sa.Column("financial_evidence_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("financial_evidences.id", ondelete="CASCADE"), nullable=True),
        sa.Column("geofence_match", sa.Boolean, nullable=True),
        sa.Column("geofence_distance_meters", sa.Float, nullable=True),
        sa.Column("timestamp_valid", sa.Boolean, nullable=True),
        sa.Column("tampering_detected", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("ai_confidence_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("raw_details", postgresql.JSONB, nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "(evidence_id IS NOT NULL AND financial_evidence_id IS NULL) OR (evidence_id IS NULL AND financial_evidence_id IS NOT NULL)",
            name="chk_verification_result_target",
        ),
    )
    op.create_index("ix_verification_results_evidence_id", "verification_results", ["evidence_id"])
    op.create_index("ix_verification_results_financial_evidence_id", "verification_results", ["financial_evidence_id"])

    # ── 7. risk_assessments ───────────────────────────────────────────────────
    op.create_table(
        "risk_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("risk_level", sa.Enum(name="risklevel"), nullable=False),
        sa.Column("risk_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("factors", postgresql.JSONB, nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="chk_risk_score_range"),
    )
    op.create_index("ix_risk_assessments_project_id", "risk_assessments", ["project_id"])
    op.create_index("ix_risk_assessments_risk_level", "risk_assessments", ["risk_level"])

    # ── 8. audits & audit_decisions ───────────────────────────────────────────
    op.create_table(
        "audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("auditor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.Enum(name="auditstatus"), nullable=False, server_default="INITIATED"),
        sa.Column("scope", sa.String(500), nullable=True),
        sa.Column("findings", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audits_project_id", "audits", ["project_id"])
    op.create_index("ix_audits_auditor_id", "audits", ["auditor_id"])
    op.create_index("ix_audits_status", "audits", ["status"])

    op.create_table(
        "audit_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("audits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision", sa.Enum(name="auditdecisiontype"), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_decisions_audit_id", "audit_decisions", ["audit_id"])
    op.create_index("ix_audit_decisions_decision", "audit_decisions", ["decision"])

    # ── 9. score_snapshots ────────────────────────────────────────────────────
    op.create_table(
        "score_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("ngo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ngos.id", ondelete="CASCADE"), nullable=True),
        sa.Column("composite_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("breakdown", postgresql.JSONB, nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("composite_score >= 0 AND composite_score <= 100", name="chk_composite_score_range"),
        sa.CheckConstraint("project_id IS NOT NULL OR ngo_id IS NOT NULL", name="chk_snapshot_has_target"),
    )
    op.create_index("ix_score_snapshots_project_id", "score_snapshots", ["project_id"])
    op.create_index("ix_score_snapshots_ngo_id", "score_snapshots", ["ngo_id"])
    op.create_index("ix_score_snapshots_calculated_at", "score_snapshots", ["calculated_at"])

    # ── 10. disputes ──────────────────────────────────────────────────────────
    op.create_table(
        "disputes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raised_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("status", sa.Enum(name="disputestatus"), nullable=False, server_default="OPEN"),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_disputes_project_id", "disputes", ["project_id"])
    op.create_index("ix_disputes_raised_by_id", "disputes", ["raised_by_id"])
    op.create_index("ix_disputes_status", "disputes", ["status"])

    # ── 11. activity_logs ─────────────────────────────────────────────────────
    op.create_table(
        "activity_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("action", sa.String(200), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_role", sa.String(50), nullable=True),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("detail", postgresql.JSONB, nullable=True),
        sa.Column("success", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_activity_logs_action", "activity_logs", ["action"])
    op.create_index("ix_activity_logs_actor_id", "activity_logs", ["actor_id"])
    op.create_index("ix_activity_logs_resource_type", "activity_logs", ["resource_type"])
    op.create_index("ix_activity_logs_created_at", "activity_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("activity_logs")
    op.drop_table("disputes")
    op.drop_table("score_snapshots")
    op.drop_table("audit_decisions")
    op.drop_table("audits")
    op.drop_table("risk_assessments")
    op.drop_table("verification_results")
    op.drop_table("financial_evidences")
    op.drop_table("evidences")
    op.drop_table("projects")
    op.drop_table("users")
    op.drop_table("ngos")

    for enum_name in (
        "disputestatus",
        "auditdecisiontype",
        "auditstatus",
        "risklevel",
        "verificationstatus",
        "evidencetype",
        "verificationmodel",
        "projectstatus",
        "projecttype",
        "userrole",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

    op.execute("DROP EXTENSION IF EXISTS postgis")
