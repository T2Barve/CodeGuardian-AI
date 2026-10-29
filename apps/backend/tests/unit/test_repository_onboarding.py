import pytest
from httpx import ASGITransport, AsyncClient

from app.github.security import parse_and_validate_github_url
from app.main import app


def test_parse_and_validate_github_url_success():
    owner, repo = parse_and_validate_github_url("https://github.com/pallets/flask")
    assert owner == "pallets"
    assert repo == "flask"

    owner2, repo2 = parse_and_validate_github_url("https://github.com/torvalds/linux.git")
    assert owner2 == "torvalds"
    assert repo2 == "linux"

    owner3, repo3 = parse_and_validate_github_url("tiangolo/fastapi")
    assert owner3 == "tiangolo"
    assert repo3 == "fastapi"


def test_parse_and_validate_github_url_security_rejections():
    # SSRF / localhost rejection
    with pytest.raises(ValueError, match="prohibited host"):
        parse_and_validate_github_url("http://169.254.169.254/latest/meta-data")

    with pytest.raises(ValueError, match="prohibited host"):
        parse_and_validate_github_url("http://localhost:8000/owner/repo")

    # Non-GitHub host rejection
    with pytest.raises(ValueError, match="Invalid repository host"):
        parse_and_validate_github_url("https://gitlab.com/owner/repo")

    # Path traversal rejection
    with pytest.raises(ValueError):
        parse_and_validate_github_url("https://github.com/owner/../malicious/repo")


@pytest.mark.asyncio
async def test_repository_validate_and_onboarding_lifecycle(async_client, monkeypatch):
    from unittest.mock import AsyncMock
    from app.github.client import GitHubClient

    mock_repo_meta = {
        "id": 987654321,
        "name": "secure-core",
        "full_name": "test-org/secure-core",
        "owner": {"login": "test-org"},
        "html_url": "https://github.com/test-org/secure-core",
        "default_branch": "main",
        "language": "Python",
        "description": "Core security library",
        "private": False,
        "open_issues_count": 3,
    }
    monkeypatch.setattr(GitHubClient, "get_repository", AsyncMock(return_value=mock_repo_meta))

    client = async_client
    # 1. Validate repository URL
    val_resp = await client.post(
        "/api/v1/repositories/validate",
        json={"url": "https://github.com/test-org/secure-core"},
    )
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["owner"] == "test-org"
    assert val_data["name"] == "secure-core"
    assert val_data["monitoring_status"] in ["READY_TO_CONNECT", "ALREADY_CONNECTED"]


    # 2. Reject malformed or SSRF URL
    bad_val = await client.post(
        "/api/v1/repositories/validate",
        json={"url": "http://169.254.169.254/secret"},
    )
    assert bad_val.status_code == 400

    # 3. Onboard repository
    create_resp = await client.post(
        "/api/v1/repositories",
        json={
            "url": "https://github.com/test-org/secure-core",
            "default_branch": "main",
            "language": "Python",
            "is_active": True,
            "auto_sync_prs": False,
        },
    )
    assert create_resp.status_code == 201
    repo_data = create_resp.json()
    repo_id = repo_data["id"]
    assert repo_data["name"] == "secure-core"
    assert repo_data["is_active"] is True

    # 4. Idempotent re-submission does not duplicate
    re_create = await client.post(
        "/api/v1/repositories",
        json={
            "url": "https://github.com/test-org/secure-core",
            "is_active": True,
            "auto_sync_prs": False,
        },
    )
    assert re_create.status_code == 201
    assert re_create.json()["id"] == repo_id

    # 5. Toggle monitoring
    mon_resp = await client.patch(
        f"/api/v1/repositories/{repo_id}/monitoring",
        json={"is_active": False},
    )
    assert mon_resp.status_code == 200
    assert mon_resp.json()["is_active"] is False

    # 6. List repositories
    list_resp = await client.get("/api/v1/repositories")
    assert list_resp.status_code == 200
    repos = list_resp.json()
    assert any(r["id"] == repo_id for r in repos)

    # 7. Pull requests endpoint
    prs_resp = await client.get("/api/v1/pull-requests")
    assert prs_resp.status_code == 200
    assert "items" in prs_resp.json()

    # 8. Scanners endpoint
    scanners_resp = await client.get("/api/v1/scanners")
    assert scanners_resp.status_code == 200
    s_data = scanners_resp.json()
    assert s_data["total_tools"] == 4
    assert any(t["name"] == "bandit" for t in s_data["tools"])

    # 9. Agents status endpoint
    agents_resp = await client.get("/api/v1/agents/status")
    assert agents_resp.status_code == 200
    a_data = agents_resp.json()
    assert len(a_data["agents"]) >= 6

    # 10. Integrations status endpoint
    integ_resp = await client.get("/api/v1/integrations/status")
    assert integ_resp.status_code == 200
    i_data = integ_resp.json()
    assert len(i_data["components"]) >= 5

    # 11. Findings explorer endpoint
    findings_resp = await client.get("/api/v1/findings")
    assert findings_resp.status_code == 200
    assert "items" in findings_resp.json()

    # 12. Fix PRs listing endpoint
    fix_prs_resp = await client.get("/api/v1/fix-prs")
    assert fix_prs_resp.status_code == 200
    assert isinstance(fix_prs_resp.json(), list)

    # 13. Audit logs endpoint
    audit_resp = await client.get("/api/v1/audit/logs")
    assert audit_resp.status_code == 200
    assert "items" in audit_resp.json()

    # 14. Delete repository safely
    del_resp = await client.delete(f"/api/v1/repositories/{repo_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "DELETED"
