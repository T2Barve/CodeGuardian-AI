import hashlib
import hmac
import json
import pytest
from httpx import AsyncClient

from app.config.settings import settings
from app.github.security import (
    clear_memory_delivery_store,
    sanitize_identifier,
    verify_hmac_signature,
)


def compute_test_signature(payload_bytes: bytes, secret: str) -> str:
    """Computes a valid X-Hub-Signature-256 header value."""
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def create_sample_pr_payload(
    action: str = "opened",
    pr_number: int = 42,
    repo_name: str = "sample-repo",
    repo_owner: str = "acme-corp",
    head_sha: str = "a1b2c3d4e5f67890123456789012345678901234",
    head_ref: str = "feature/auth-service",
    base_ref: str = "main",
) -> dict:
    """Generates a realistic GitHub Pull Request webhook payload structure."""
    return {
        "action": action,
        "number": pr_number,
        "pull_request": {
            "id": 98765000 + pr_number,
            "number": pr_number,
            "title": f"feat: implement authentication logic #{pr_number}",
            "state": "open" if action != "closed" else "closed",
            "body": "PR description detailing OAuth2 and JWT validation.",
            "head": {
                "ref": head_ref,
                "sha": head_sha,
                "repo": {
                    "id": 12345678,
                    "name": repo_name,
                    "full_name": f"{repo_owner}/{repo_name}",
                    "owner": {"id": 5555, "login": repo_owner, "type": "Organization"},
                    "html_url": f"https://github.com/{repo_owner}/{repo_name}",
                    "default_branch": "main",
                    "language": "python",
                    "private": False,
                },
                "user": {"id": 1111, "login": "developer-alice", "type": "User"},
            },
            "base": {
                "ref": base_ref,
                "sha": "0000000000000000000000000000000000000000",
                "repo": {
                    "id": 12345678,
                    "name": repo_name,
                    "full_name": f"{repo_owner}/{repo_name}",
                    "owner": {"id": 5555, "login": repo_owner, "type": "Organization"},
                    "html_url": f"https://github.com/{repo_owner}/{repo_name}",
                    "default_branch": "main",
                    "language": "python",
                    "private": False,
                },
                "user": {"id": 5555, "login": repo_owner, "type": "Organization"},
            },
            "user": {"id": 1111, "login": "developer-alice", "type": "User"},
            "html_url": f"https://github.com/{repo_owner}/{repo_name}/pull/{pr_number}",
            "merged": False,
        },
        "repository": {
            "id": 12345678,
            "name": repo_name,
            "full_name": f"{repo_owner}/{repo_name}",
            "owner": {"id": 5555, "login": repo_owner, "type": "Organization"},
            "html_url": f"https://github.com/{repo_owner}/{repo_name}",
            "default_branch": "main",
            "language": "python",
            "private": False,
        },
        "sender": {"id": 1111, "login": "developer-alice", "type": "User"},
    }


@pytest.mark.asyncio
async def test_webhook_valid_hmac_enqueues_job(async_client: AsyncClient):
    """Verifies that a valid HMAC signature and actionable PR event enqueues a ReviewJob."""
    payload_dict = create_sample_pr_payload(action="opened", pr_number=101)
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    delivery_id = "test-delivery-valid-001"
    signature = compute_test_signature(payload_bytes, settings.GITHUB_WEBHOOK_SECRET)

    response = await async_client.post(
        "/api/v1/github/webhook",
        content=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": delivery_id,
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "enqueued"
    assert data["delivery_id"] == delivery_id
    assert data["event"] == "pull_request"
    assert data["action"] == "opened"
    assert data["job_id"] is not None
    assert len(data["job_id"]) == 36  # UUID length


@pytest.mark.asyncio
async def test_webhook_invalid_hmac_signature_rejected(async_client: AsyncClient):
    """Verifies that an altered or forged HMAC signature returns 401 Unauthorized."""
    payload_dict = create_sample_pr_payload(action="opened", pr_number=102)
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    delivery_id = "test-delivery-invalid-hmac-002"
    invalid_signature = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

    response = await async_client.post(
        "/api/v1/github/webhook",
        content=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": delivery_id,
            "X-Hub-Signature-256": invalid_signature,
        },
    )

    assert response.status_code == 401
    data = response.json()
    assert data["status"] == 401
    assert "Invalid signature" in data.get("title", "") or "signature" in data.get("detail", "").lower()


@pytest.mark.asyncio
async def test_webhook_missing_headers_rejected(async_client: AsyncClient):
    """Verifies rejection when mandatory security/delivery headers are omitted."""
    payload_bytes = json.dumps(create_sample_pr_payload()).encode("utf-8")
    signature = compute_test_signature(payload_bytes, settings.GITHUB_WEBHOOK_SECRET)

    # 1. Missing X-Hub-Signature-256
    resp1 = await async_client.post(
        "/api/v1/github/webhook",
        content=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "del-001",
        },
    )
    assert resp1.status_code == 401

    # 2. Missing X-GitHub-Event
    resp2 = await async_client.post(
        "/api/v1/github/webhook",
        content=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Delivery": "del-002",
            "X-Hub-Signature-256": signature,
        },
    )
    assert resp2.status_code == 400

    # 3. Missing X-GitHub-Delivery
    resp3 = await async_client.post(
        "/api/v1/github/webhook",
        content=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": signature,
        },
    )
    assert resp3.status_code == 400


@pytest.mark.asyncio
async def test_webhook_idempotency_duplicate_delivery_conflict(async_client: AsyncClient):
    """Verifies that re-sending the same delivery ID within 24h returns 409 Conflict."""
    payload_dict = create_sample_pr_payload(action="opened", pr_number=103)
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    delivery_id = "test-replay-uuid-003"
    signature = compute_test_signature(payload_bytes, settings.GITHUB_WEBHOOK_SECRET)

    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": delivery_id,
        "X-Hub-Signature-256": signature,
    }

    # First delivery: success (202)
    resp1 = await async_client.post("/api/v1/github/webhook", content=payload_bytes, headers=headers)
    assert resp1.status_code == 202

    # Second delivery with identical delivery_id: Conflict (409)
    resp2 = await async_client.post("/api/v1/github/webhook", content=payload_bytes, headers=headers)
    assert resp2.status_code == 409
    data = resp2.json()
    assert data["status"] == 409
    assert "duplicate" in data["detail"].lower()


@pytest.mark.asyncio
async def test_webhook_malformed_json_payload(async_client: AsyncClient):
    """Verifies that non-JSON garbage returns 400 Bad Request."""
    malformed_bytes = b"NOT_A_VALID_JSON_STRING{{{{"
    delivery_id = "test-malformed-004"
    signature = compute_test_signature(malformed_bytes, settings.GITHUB_WEBHOOK_SECRET)

    response = await async_client.post(
        "/api/v1/github/webhook",
        content=malformed_bytes,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": delivery_id,
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert data["status"] == 400
    assert "malformed" in data["detail"].lower()


@pytest.mark.asyncio
async def test_webhook_unsupported_event_type(async_client: AsyncClient):
    """Verifies that non-PR events (e.g. issues, push) return 400 Bad Request."""
    payload_bytes = b'{"action": "created"}'
    delivery_id = "test-issues-event-005"
    signature = compute_test_signature(payload_bytes, settings.GITHUB_WEBHOOK_SECRET)

    response = await async_client.post(
        "/api/v1/github/webhook",
        content=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": delivery_id,
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert data["status"] == 400
    assert "unsupported" in data["detail"].lower()


@pytest.mark.asyncio
async def test_webhook_non_actionable_pr_action_acknowledged(async_client: AsyncClient):
    """Verifies that closed/labeled PR actions return 202 with status='ignored' and job_id=None."""
    payload_dict = create_sample_pr_payload(action="closed", pr_number=104)
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    delivery_id = "test-closed-action-006"
    signature = compute_test_signature(payload_bytes, settings.GITHUB_WEBHOOK_SECRET)

    response = await async_client.post(
        "/api/v1/github/webhook",
        content=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": delivery_id,
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "ignored"
    assert data["job_id"] is None
    assert data["action"] == "closed"


@pytest.mark.asyncio
async def test_webhook_synchronize_action_triggers_review(async_client: AsyncClient):
    """Verifies that 'synchronize' (new commits pushed to PR) triggers a new review job."""
    payload_dict = create_sample_pr_payload(action="synchronize", pr_number=105)
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    delivery_id = "test-sync-action-007"
    signature = compute_test_signature(payload_bytes, settings.GITHUB_WEBHOOK_SECRET)

    response = await async_client.post(
        "/api/v1/github/webhook",
        content=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": delivery_id,
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "enqueued"
    assert data["action"] == "synchronize"
    assert data["job_id"] is not None


def test_verify_hmac_signature_helper():
    """Unit tests for verify_hmac_signature standalone function."""
    secret = "super_secret_test_key_12345"
    body = b"{\"event\": \"test_data\"}"
    correct_sig = compute_test_signature(body, secret)

    # Valid signature
    assert verify_hmac_signature(body, correct_sig, secret) is True

    # Altered body
    assert verify_hmac_signature(b"{\"event\": \"altered\"}", correct_sig, secret) is False

    # Missing / None header
    assert verify_hmac_signature(body, None, secret) is False

    # Header without sha256= prefix
    assert verify_hmac_signature(body, "invalid_prefix_digest", secret) is False

    # Empty secret
    assert verify_hmac_signature(body, correct_sig, "") is False


def test_sanitize_identifier_helper():
    """Unit tests for sanitize_identifier security constraints."""
    # Valid identifiers
    assert sanitize_identifier("acme-corp") == "acme-corp"
    assert sanitize_identifier("ecommerce_backend.v2") == "ecommerce_backend.v2"
    assert sanitize_identifier("feat/auth-service") == "feat/auth-service"

    # Path traversal rejected
    with pytest.raises(ValueError, match="path traversal"):
        sanitize_identifier("../../etc/passwd", "file")

    with pytest.raises(ValueError, match="path traversal"):
        sanitize_identifier("repo\\subdir", "repo")

    # Command injection characters rejected
    with pytest.raises(ValueError, match="invalid characters"):
        sanitize_identifier("repo; rm -rf /", "repo")

    with pytest.raises(ValueError, match="invalid characters"):
        sanitize_identifier("branch$(whoami)", "branch")

    # Empty identifier rejected
    with pytest.raises(ValueError, match="cannot be empty"):
        sanitize_identifier("", "empty")
