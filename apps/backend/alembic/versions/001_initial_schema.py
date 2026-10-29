"""Initial schema migration for CodeGuardian AI

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("github_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column("role", sa.String(32), server_default="DEVELOPER", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_users_github_id", "users", ["github_id"], unique=True)
    op.create_index("idx_users_username", "users", ["username"])

    # 2. repositories
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("github_repo_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("default_branch", sa.String(100), server_default="main", nullable=False),
        sa.Column("language", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_repositories_github_repo_id", "repositories", ["github_repo_id"], unique=True)
    op.create_index("idx_repositories_owner_name", "repositories", ["owner", "name"])

    # 3. pull_requests
    op.create_table(
        "pull_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("github_pr_id", sa.BigInteger(), nullable=False),
        sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("author", sa.String(255), nullable=False),
        sa.Column("source_branch", sa.String(255), nullable=False),
        sa.Column("target_branch", sa.String(255), nullable=False),
        sa.Column("commit_sha", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="OPEN", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("repository_id", "number", name="uq_repo_pr_number"),
    )
    op.create_index("idx_pull_requests_github_pr_id", "pull_requests", ["github_pr_id"], unique=True)
    op.create_index("idx_pull_requests_repo_number", "pull_requests", ["repository_id", "number"])

    # 4. review_jobs
    op.create_table(
        "review_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pull_request_id", sa.String(36), sa.ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), server_default="QUEUED", nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index("idx_review_jobs_status", "review_jobs", ["status"])

    # 5. review_runs
    op.create_table(
        "review_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_job_id", sa.String(36), sa.ForeignKey("review_jobs.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), server_default="RUNNING", nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("risk_grade", sa.String(8), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
    )

    # 6. findings
    op.create_table(
        "findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_run_id", sa.String(36), sa.ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(32), server_default="OPEN", nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("impact", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("policy_reference", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_findings_run_id", "findings", ["review_run_id"])
    op.create_index("idx_findings_fingerprint", "findings", ["fingerprint"])
    op.create_index("idx_findings_severity", "findings", ["severity"])

    # 7. finding_evidence
    op.create_table(
        "finding_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("finding_id", sa.String(36), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("tool", sa.String(64), nullable=False),
        sa.Column("rule_id", sa.String(128), nullable=True),
        sa.Column("raw_message", sa.Text(), nullable=False),
        sa.Column("code_snippet", sa.Text(), nullable=True),
        sa.Column("metadata_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_finding_evidence_finding_id", "finding_evidence", ["finding_id"])

    # 8. agent_runs
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_run_id", sa.String(36), sa.ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("input_reference", sa.JSON(), nullable=True),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completion_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("estimated_cost", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_agent_runs_review_run", "agent_runs", ["review_run_id", "agent_name"])

    # 9. policies
    op.create_table(
        "policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("version", sa.String(32), server_default="1.0.0", nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_policies_category", "policies", ["category"])

    # 10. policy_chunks
    op.create_table(
        "policy_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("policy_id", sa.String(36), sa.ForeignKey("policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding_reference", sa.String(128), nullable=False),
        sa.Column("metadata_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_policy_chunks_policy_id", "policy_chunks", ["policy_id"])

    # 11. remediation_attempts
    op.create_table(
        "remediation_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("finding_id", sa.String(36), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("patch", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), server_default="REQUESTED", nullable=False),
        sa.Column("validation_result", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_remediation_attempts_finding_id", "remediation_attempts", ["finding_id"])

    # 12. fix_prs
    op.create_table(
        "fix_prs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("remediation_attempt_id", sa.String(36), sa.ForeignKey("remediation_attempts.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("github_pr_id", sa.BigInteger(), nullable=True),
        sa.Column("number", sa.Integer(), nullable=True),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("status", sa.String(32), server_default="OPEN", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 13. audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=False),
        sa.Column("metadata_payload", sa.JSON(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("idx_audit_logs_timestamp", "audit_logs", ["timestamp"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("fix_prs")
    op.drop_table("remediation_attempts")
    op.drop_table("policy_chunks")
    op.drop_table("policies")
    op.drop_table("agent_runs")
    op.drop_table("finding_evidence")
    op.drop_table("findings")
    op.drop_table("review_runs")
    op.drop_table("review_jobs")
    op.drop_table("pull_requests")
    op.drop_table("repositories")
    op.drop_table("users")
