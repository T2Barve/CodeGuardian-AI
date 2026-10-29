from typing import Any, Dict, List, Optional
import httpx
from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger("codeguardian.github.client")


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class GitHubNotFoundError(GitHubAPIError):
    """Raised when a GitHub resource (repository, PR, file) is not found (404)."""
    pass


class GitHubAuthError(GitHubAPIError):
    """Raised when GitHub authentication or authorization fails (401/403)."""
    pass


class GitHubClient:
    """
    Asynchronous GitHub REST API client for repository inspection,
    PR diff retrieval, check runs, comments, and automated Fix PRs.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = "https://api.github.com",
        timeout: float = 30.0,
    ):
        self._explicit_token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def token(self) -> str:
        return self._explicit_token if self._explicit_token is not None else settings.GITHUB_TOKEN

    @token.setter
    def token(self, value: Optional[str]) -> None:
        self._explicit_token = value

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": f"CodeGuardian-AI/{settings.VERSION}",
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Closes the underlying HTTP client session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "GitHubClient":
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def _request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
    ) -> httpx.Response:
        client = await self._get_client()
        req_headers = dict(client.headers)
        if headers:
            req_headers.update(headers)

        response = await client.request(
            method=method,
            url=path,
            headers=req_headers,
            params=params,
            json=json,
        )

        # Inspect rate limiting telemetry
        remaining = response.headers.get("x-ratelimit-remaining")
        if remaining and int(remaining) < 20:
            logger.warning("GitHub API rate limit remaining low", extra={"remaining": remaining})

        if response.status_code == 401 or response.status_code == 403:
            raise GitHubAuthError(
                f"GitHub API authentication/authorization failed: {response.text}",
                status_code=response.status_code,
                response_body=response.text,
            )
        elif response.status_code == 404:
            raise GitHubNotFoundError(
                f"GitHub resource not found at {path}: {response.text}",
                status_code=404,
                response_body=response.text,
            )
        elif response.is_error:
            raise GitHubAPIError(
                f"GitHub API error ({response.status_code}) on {method} {path}: {response.text}",
                status_code=response.status_code,
                response_body=response.text,
            )

        return response

    async def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetches full metadata for a repository (public or authorized private)."""
        resp = await self._request("GET", f"/repos/{owner}/{repo}")
        return resp.json()

    async def get_pull_requests_count(self, owner: str, repo: str, state: str = "open") -> int:
        """
        Retrieves the exact pull request count for a repository using official GitHub API
        header pagination (rel='last') with per_page=1 to minimize bandwidth and latency.
        Handles zero-result, single-result, and multi-page repositories correctly.
        """
        import re
        try:
            resp = await self._request(
                "GET",
                f"/repos/{owner}/{repo}/pulls",
                params={"state": state, "per_page": 1},
            )
            data = resp.json()
            if not isinstance(data, list) or len(data) == 0:
                return 0
            link_header = resp.headers.get("link", "")
            if not link_header:
                return len(data)
            match = re.search(r'[?&]page=(\d+)[^>]*>;\s*rel="last"', link_header)
            if match:
                return int(match.group(1))
            return len(data)
        except Exception as exc:
            logger.warning(
                f"Failed to fetch exact {state} pull request count for {owner}/{repo}: {exc}"
            )
            return 0

    async def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        page: int = 1,
        per_page: int = 30,
    ) -> List[Dict[str, Any]]:
        """Lists pull requests for a repository with page pagination."""
        resp = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls",
            params={"state": state, "page": page, "per_page": per_page, "sort": "updated", "direction": "desc"},
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    async def list_user_repositories(self, per_page: int = 50) -> List[Dict[str, Any]]:
        """Lists repositories accessible to the authenticated token."""
        resp = await self._request(
            "GET",
            "/user/repos",
            params={"sort": "updated", "per_page": per_page},
        )
        return resp.json()

    async def get_pull_request(self, owner: str, repo: str, pull_number: int) -> Dict[str, Any]:
        """Fetches full metadata for a pull request."""
        resp = await self._request("GET", f"/repos/{owner}/{repo}/pulls/{pull_number}")
        return resp.json()

    async def get_pull_request_files(
        self, owner: str, repo: str, pull_number: int, page: int = 1, per_page: int = 100
    ) -> List[Dict[str, Any]]:
        """Lists files changed in a pull request."""
        resp = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{pull_number}/files",
            params={"page": page, "per_page": per_page},
        )
        return resp.json()

    async def get_pull_request_diff(self, owner: str, repo: str, pull_number: int) -> str:
        """Retrieves raw unified git diff for a pull request."""
        resp = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{pull_number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        return resp.text

    async def get_commit(self, owner: str, repo: str, commit_sha: str) -> Dict[str, Any]:
        """Retrieves a single commit by SHA."""
        resp = await self._request("GET", f"/repos/{owner}/{repo}/commits/{commit_sha}")
        return resp.json()

    async def create_check_run(
        self,
        owner: str,
        repo: str,
        name: str,
        head_sha: str,
        status: str = "in_progress",
        conclusion: Optional[str] = None,
        output: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Creates a GitHub Check Run on a commit SHA."""
        payload: Dict[str, Any] = {
            "name": name,
            "head_sha": head_sha,
            "status": status,
        }
        if conclusion:
            payload["conclusion"] = conclusion
        if output:
            payload["output"] = output

        resp = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/check-runs",
            json=payload,
        )
        return resp.json()

    async def update_check_run(
        self,
        owner: str,
        repo: str,
        check_run_id: int,
        status: str,
        conclusion: Optional[str] = None,
        output: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Updates an existing GitHub Check Run."""
        payload: Dict[str, Any] = {"status": status}
        if conclusion:
            payload["conclusion"] = conclusion
        if output:
            payload["output"] = output

        resp = await self._request(
            "PATCH",
            f"/repos/{owner}/{repo}/check-runs/{check_run_id}",
            json=payload,
        )
        return resp.json()

    async def list_issue_comments(
        self, owner: str, repo: str, issue_number: int, per_page: int = 100
    ) -> List[Dict[str, Any]]:
        """Lists comments on a pull request issue thread."""
        resp = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            params={"per_page": per_page},
        )
        return resp.json()

    async def update_issue_comment(
        self, owner: str, repo: str, comment_id: int, body: str
    ) -> Dict[str, Any]:
        """Updates an existing issue comment."""
        resp = await self._request(
            "PATCH",
            f"/repos/{owner}/{repo}/issues/comments/{comment_id}",
            json={"body": body},
        )
        return resp.json()

    async def list_check_runs_for_ref(
        self, owner: str, repo: str, ref: str
    ) -> Dict[str, Any]:
        """Lists check runs for a specific commit ref or SHA."""
        resp = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/commits/{ref}/check-runs",
        )
        return resp.json()

    async def create_issue_comment(
        self, owner: str, repo: str, issue_number: int, body: str
    ) -> Dict[str, Any]:
        """Posts a comment on a pull request issue thread."""
        resp = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": body},
        )
        return resp.json()

    async def create_pull_request_review_comment(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        body: str,
        commit_id: str,
        path: str,
        line: int,
    ) -> Dict[str, Any]:
        """Posts an inline review comment on a specific file and line."""
        payload = {
            "body": body,
            "commit_id": commit_id,
            "path": path,
            "line": line,
        }
        resp = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls/{pull_number}/comments",
            json=payload,
        )
        return resp.json()

    async def create_branch(
        self, owner: str, repo: str, branch_name: str, base_sha: str
    ) -> Dict[str, Any]:
        """Creates a new git reference/branch from a base commit SHA."""
        payload = {
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha,
        }
        resp = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/git/refs",
            json=payload,
        )
        return resp.json()

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str,
    ) -> Dict[str, Any]:
        """Submits a new pull request (e.g. automated Fix PR)."""
        payload = {
            "title": title,
            "head": head,
            "base": base,
            "body": body,
        }
        resp = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            json=payload,
        )
        return resp.json()

    async def get_file_contents(
        self, owner: str, repo: str, path: str, ref: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieves file metadata and base64 content from repository."""
        params = {"ref": ref} if ref else {}
        resp = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{path.lstrip('/')}",
            params=params,
        )
        return resp.json()

    async def create_or_update_file_contents(
        self,
        owner: str,
        repo: str,
        path: str,
        message: str,
        content_base64: str,
        branch: str,
        sha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates or updates a file in a repository on a specific branch."""
        payload: Dict[str, Any] = {
            "message": message,
            "content": content_base64,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        resp = await self._request(
            "PUT",
            f"/repos/{owner}/{repo}/contents/{path.lstrip('/')}",
            json=payload,
        )
        return resp.json()

