import pytest
import httpx
from unittest.mock import AsyncMock, patch

from app.github.client import (
    GitHubClient,
    GitHubAPIError,
    GitHubNotFoundError,
    GitHubAuthError,
)


@pytest.mark.asyncio
async def test_github_client_get_pull_request():
    """Verifies fetching PR metadata via GitHubClient."""
    mock_pr_response = {
        "id": 123456,
        "number": 42,
        "title": "feat: add secure auth flow",
        "state": "open",
        "head": {"sha": "abcdef1234567890"},
    }

    client = GitHubClient(token="mock-token-xyz")
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_response = httpx.Response(
            status_code=200,
            json=mock_pr_response,
            request=httpx.Request("GET", "https://api.github.com/repos/acme/backend/pulls/42"),
        )
        mock_req.return_value = mock_response

        pr = await client.get_pull_request("acme", "backend", 42)
        assert pr["number"] == 42
        assert pr["title"] == "feat: add secure auth flow"
        mock_req.assert_called_once_with("GET", "/repos/acme/backend/pulls/42")

    await client.close()


@pytest.mark.asyncio
async def test_github_client_get_diff():
    """Verifies fetching raw unified diff via GitHubClient."""
    sample_diff = "--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-old\n+new"
    client = GitHubClient(token="mock-token-xyz")

    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_response = httpx.Response(
            status_code=200,
            text=sample_diff,
            request=httpx.Request("GET", "https://api.github.com/repos/acme/backend/pulls/42"),
        )
        mock_req.return_value = mock_response

        diff = await client.get_pull_request_diff("acme", "backend", 42)
        assert "+++ b/main.py" in diff
        mock_req.assert_called_once_with(
            "GET",
            "/repos/acme/backend/pulls/42",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )

    await client.close()


@pytest.mark.asyncio
async def test_github_client_create_check_run():
    """Verifies creating a check run via GitHubClient."""
    client = GitHubClient(token="mock-token-xyz")

    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_response = httpx.Response(
            status_code=201,
            json={"id": 9999, "name": "CodeGuardian AI", "status": "in_progress"},
            request=httpx.Request("POST", "https://api.github.com/repos/acme/backend/check-runs"),
        )
        mock_req.return_value = mock_response

        check = await client.create_check_run(
            owner="acme",
            repo="backend",
            name="CodeGuardian AI",
            head_sha="abcdef123456",
            status="in_progress",
        )
        assert check["id"] == 9999
        assert check["status"] == "in_progress"

    await client.close()


@pytest.mark.asyncio
async def test_github_client_create_issue_comment():
    """Verifies posting a review summary comment on PR issue thread."""
    client = GitHubClient(token="mock-token-xyz")

    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_response = httpx.Response(
            status_code=201,
            json={"id": 555, "body": "Review completed: Risk Grade B (Score 22.5)"},
            request=httpx.Request("POST", "https://api.github.com/repos/acme/backend/issues/42/comments"),
        )
        mock_req.return_value = mock_response

        comment = await client.create_issue_comment(
            owner="acme",
            repo="backend",
            issue_number=42,
            body="Review completed: Risk Grade B (Score 22.5)",
        )
        assert comment["id"] == 555
        assert "Risk Grade B" in comment["body"]

    await client.close()


@pytest.mark.asyncio
async def test_github_client_error_handling():
    """Verifies that 401, 404, and 500 status codes raise appropriate typed exceptions."""
    client = GitHubClient(token="invalid-token")

    # Mock 401 Unauthorized
    transport_401 = httpx.MockTransport(
        lambda req: httpx.Response(status_code=401, text="Bad credentials")
    )
    async with httpx.AsyncClient(transport=transport_401, base_url="https://api.github.com") as mock_http:
        client._client = mock_http
        with pytest.raises(GitHubAuthError) as exc_info:
            await client.get_pull_request("acme", "backend", 1)
        assert exc_info.value.status_code == 401

    # Mock 404 Not Found
    transport_404 = httpx.MockTransport(
        lambda req: httpx.Response(status_code=404, text="Not Found")
    )
    async with httpx.AsyncClient(transport=transport_404, base_url="https://api.github.com") as mock_http:
        client._client = mock_http
        with pytest.raises(GitHubNotFoundError) as exc_info:
            await client.get_pull_request("acme", "backend", 999999)
        assert exc_info.value.status_code == 404

    # Mock 500 Internal Server Error
    transport_500 = httpx.MockTransport(
        lambda req: httpx.Response(status_code=500, text="Internal Server Error")
    )
    async with httpx.AsyncClient(transport=transport_500, base_url="https://api.github.com") as mock_http:
        client._client = mock_http
        with pytest.raises(GitHubAPIError) as exc_info:
            await client.get_pull_request("acme", "backend", 1)
        assert exc_info.value.status_code == 500

    await client.close()
