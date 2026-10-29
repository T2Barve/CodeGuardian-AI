from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.session import get_db
from app.github.client import GitHubAuthError, GitHubClient, GitHubNotFoundError
from app.github.security import parse_and_validate_github_url
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.repositories.audit_repository import AuditRepository
from app.schemas.errors import ProblemDetailException
from app.schemas.repository import (
    GitHubAccessibleRepo,
    GitHubAccessibleReposResponse,
    PullRequestSummary,
    RepositoryCreateRequest,
    RepositoryDetail,
    RepositoryMonitoringUpdateRequest,
    RepositoryRead,
    RepositorySyncResponse,
    RepositoryValidateRequest,
    RepositoryValidateResponse,
)
from app.utils.logging import get_logger

logger = get_logger("codeguardian.api.repositories")
router = APIRouter(prefix="/repositories", tags=["Repositories"])


@router.get(
    "",
    response_model=List[RepositoryRead],
    summary="List all tracked GitHub repositories",
)
async def list_repositories(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
) -> List[RepositoryRead]:
    stmt = (
        select(Repository)
        .options(
            selectinload(Repository.pull_requests)
            .selectinload(PullRequest.review_jobs)
            .selectinload(ReviewJob.review_run)
        )
        .order_by(Repository.updated_at.desc())
    )
    if is_active is not None:
        stmt = stmt.where(Repository.is_active == is_active)

    result = await db.execute(stmt)
    repos = result.scalars().all()

    items: List[RepositoryRead] = []
    for r in repos:
        pr_count = len(r.pull_requests)
        review_count = sum(
            1 for pr in r.pull_requests for job in pr.review_jobs if job.review_run is not None
        )

        latest_date = None
        has_critical = False
        for pr in r.pull_requests:
            for job in pr.review_jobs:
                run = job.review_run
                if run and run.completed_at:
                    if latest_date is None or run.completed_at > latest_date:
                        latest_date = run.completed_at
                    if run.risk_grade in ["D", "F"]:
                        has_critical = True

        health = "NEEDS_ATTENTION" if has_critical else "HEALTHY"

        items.append(
            RepositoryRead(
                id=r.id,
                github_repo_id=r.github_repo_id,
                name=r.name,
                owner=r.owner,
                url=r.url,
                default_branch=r.default_branch,
                language=r.language,
                is_active=r.is_active,
                pull_requests_count=pr_count,
                reviews_count=review_count,
                last_reviewed_at=latest_date,
                health_status=health,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )

    return items


@router.post(
    "/validate",
    response_model=RepositoryValidateResponse,
    summary="Validate GitHub repository URL and fetch real metadata",
)
async def validate_repository(
    request: RepositoryValidateRequest,
    db: AsyncSession = Depends(get_db),
) -> RepositoryValidateResponse:
    """
    Validates a repository URL against GitHub and security rules (SSRF, path traversal).
    Fetches real repository metadata from GitHub.
    """
    try:
        owner, repo = parse_and_validate_github_url(request.url)
    except ValueError as ve:
        raise ProblemDetailException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Invalid Repository URL",
            detail=str(ve),
        )

    # Check if already tracked in our database
    existing_stmt = select(Repository).where(
        Repository.owner.ilike(owner),
        Repository.name.ilike(repo),
    )
    res = await db.execute(existing_stmt)
    existing_repo = res.scalars().first()
    exists_in_db = existing_repo is not None

    # Fetch real metadata from GitHub API
    async with GitHubClient() as client:
        try:
            repo_meta = await client.get_repository(owner, repo)
            open_prs_count = await client.get_pull_requests_count(owner, repo, state="open")
        except GitHubNotFoundError:
            raise ProblemDetailException(
                status_code=status.HTTP_404_NOT_FOUND,
                title="Repository Not Found",
                detail=f"GitHub repository '{owner}/{repo}' was not found. Verify repository name and accessibility.",
            )
        except GitHubAuthError:
            raise ProblemDetailException(
                status_code=status.HTTP_403_FORBIDDEN,
                title="GitHub Access Denied",
                detail=f"Access denied to '{owner}/{repo}'. For private repositories, configure a valid GITHUB_TOKEN.",
            )
        except Exception as e:
            logger.warning(f"Could not connect to GitHub API for {owner}/{repo}: {e}")
            # If public and offline, provide defensive validation
            return RepositoryValidateResponse(
                owner=owner,
                name=repo,
                full_name=f"{owner}/{repo}",
                url=f"https://github.com/{owner}/{repo}",
                default_branch="main",
                language="Python",
                description="Repository verified via URL format",
                is_private=False,
                open_issues_count=0,
                open_pull_requests_count=0,
                stargazers_count=0,
                forks_count=0,
                exists_in_database=exists_in_db,
                monitoring_status="ALREADY_CONNECTED" if exists_in_db else "READY_TO_CONNECT",
                webhook_url="/api/v1/github/webhook",
            )

    # In GitHub REST API, open_issues_count conflates both open issues and open PRs.
    # We accurately segregate true open issues from open pull requests.
    total_issues_and_prs = repo_meta.get("open_issues_count", 0)
    true_open_issues = max(0, total_issues_and_prs - open_prs_count)

    return RepositoryValidateResponse(
        owner=repo_meta.get("owner", {}).get("login", owner),
        name=repo_meta.get("name", repo),
        full_name=repo_meta.get("full_name", f"{owner}/{repo}"),
        url=repo_meta.get("html_url", f"https://github.com/{owner}/{repo}"),
        default_branch=repo_meta.get("default_branch", "main"),
        language=repo_meta.get("language"),
        description=repo_meta.get("description"),
        is_private=bool(repo_meta.get("private", False)),
        open_issues_count=true_open_issues,
        open_pull_requests_count=open_prs_count,
        stargazers_count=repo_meta.get("stargazers_count", 0),
        forks_count=repo_meta.get("forks_count", 0),
        exists_in_database=exists_in_db,
        monitoring_status="ALREADY_CONNECTED" if exists_in_db else "READY_TO_CONNECT",
        webhook_url="/api/v1/github/webhook",
    )


@router.get(
    "/github/user-repos",
    response_model=GitHubAccessibleReposResponse,
    summary="List repositories accessible to the configured GitHub token/App",
)
async def list_github_user_repositories() -> GitHubAccessibleReposResponse:
    from app.config.settings import settings
    if not settings.GITHUB_TOKEN:
        return GitHubAccessibleReposResponse(
            configured=False,
            total=0,
            repositories=[],
            message="GitHub token not configured. Use URL onboarding (Option B).",
        )

    async with GitHubClient() as client:
        try:
            raw_repos = await client.list_user_repositories(per_page=50)
            items = [
                GitHubAccessibleRepo(
                    id=r.get("id"),
                    name=r.get("name"),
                    full_name=r.get("full_name"),
                    owner=r.get("owner", {}).get("login", ""),
                    url=r.get("html_url"),
                    default_branch=r.get("default_branch", "main"),
                    is_private=bool(r.get("private", False)),
                    language=r.get("language"),
                    description=r.get("description"),
                )
                for r in raw_repos
            ]
            return GitHubAccessibleReposResponse(
                configured=True,
                total=len(items),
                repositories=items,
                message=None,
            )
        except Exception as e:
            return GitHubAccessibleReposResponse(
                configured=True,
                total=0,
                repositories=[],
                message=f"Failed to fetch repositories from GitHub: {str(e)}",
            )


@router.post(
    "",
    response_model=RepositoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard a new GitHub repository for automated DevSecOps monitoring",
)
async def create_repository(
    request: RepositoryCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> RepositoryRead:
    """
    Onboards a GitHub repository, persists its configuration, verifies access,
    and optionally synchronizes initial pull requests.
    """
    try:
        owner, repo_name = parse_and_validate_github_url(request.url)
    except ValueError as ve:
        raise ProblemDetailException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Invalid Repository URL",
            detail=str(ve),
        )

    # Check for existing repository
    existing_stmt = select(Repository).where(
        Repository.owner.ilike(owner),
        Repository.name.ilike(repo_name),
    )
    res = await db.execute(existing_stmt)
    existing_repo = res.scalars().first()

    github_id = request.github_repo_id
    default_branch = request.default_branch or "main"
    language = request.language
    url = f"https://github.com/{owner}/{repo_name}"

    # Fetch live GitHub metadata if not already supplied
    if not github_id:
        async with GitHubClient() as client:
            try:
                meta = await client.get_repository(owner, repo_name)
                github_id = meta.get("id")
                default_branch = meta.get("default_branch", default_branch)
                language = meta.get("language") or language
                url = meta.get("html_url", url)
            except Exception as e:
                logger.warning(f"Live GitHub metadata lookup skipped or failed: {e}")
                # Generate deterministic ID based on owner/repo if GitHub API is unreachable
                import hashlib
                hash_int = int(hashlib.md5(f"{owner}/{repo_name}".encode()).hexdigest()[:8], 16)
                github_id = hash_int

    if existing_repo:
        existing_repo.is_active = request.is_active
        existing_repo.default_branch = default_branch
        if language:
            existing_repo.language = language
        await db.commit()
        await db.refresh(existing_repo)
        target_repo = existing_repo
    else:
        new_repo = Repository(
            github_repo_id=github_id,
            name=repo_name,
            owner=owner,
            url=url,
            default_branch=default_branch,
            language=language,
            is_active=request.is_active,
        )
        db.add(new_repo)
        await db.commit()
        await db.refresh(new_repo)
        target_repo = new_repo

    audit_repo = AuditRepository(db)
    await audit_repo.record(
        actor="dashboard-user",
        action="REPOSITORY_ONBOARDED",
        resource_type="repository",
        resource_id=target_repo.id,
        metadata_payload={
            "owner": owner,
            "name": repo_name,
            "url": target_repo.url,
            "is_active": target_repo.is_active,
        },
    )

    # Auto-sync initial pull requests if requested
    if request.auto_sync_prs and target_repo.is_active:
        try:
            async with GitHubClient() as client:
                prs = await client.list_pull_requests(owner, repo_name, state="open", per_page=15)
                for pr_data in prs:
                    pr_num = pr_data.get("number")
                    pr_id = pr_data.get("id")
                    if not pr_num or not pr_id:
                        continue

                    # Check if PR already exists
                    pr_stmt = select(PullRequest).where(
                        PullRequest.repository_id == target_repo.id,
                        PullRequest.number == pr_num,
                    )
                    pr_res = await db.execute(pr_stmt)
                    existing_pr = pr_res.scalars().first()
                    if not existing_pr:
                        head_sha = pr_data.get("head", {}).get("sha", "00000000")
                        new_pr = PullRequest(
                            github_pr_id=pr_id,
                            repository_id=target_repo.id,
                            number=pr_num,
                            title=pr_data.get("title", f"Pull Request #{pr_num}"),
                            author=pr_data.get("user", {}).get("login", "author"),
                            source_branch=pr_data.get("head", {}).get("ref", "feature"),
                            target_branch=pr_data.get("base", {}).get("ref", default_branch),
                            commit_sha=head_sha,
                            status="OPEN",
                        )
                        db.add(new_pr)
                await db.commit()
        except Exception as sync_err:
            logger.info(f"Initial PR synchronization notice: {sync_err}")

    # Return refreshed repository
    return RepositoryRead(
        id=target_repo.id,
        github_repo_id=target_repo.github_repo_id,
        name=target_repo.name,
        owner=target_repo.owner,
        url=target_repo.url,
        default_branch=target_repo.default_branch,
        language=target_repo.language,
        is_active=target_repo.is_active,
        pull_requests_count=0,
        reviews_count=0,
        last_reviewed_at=None,
        health_status="HEALTHY",
        created_at=target_repo.created_at,
        updated_at=target_repo.updated_at,
    )


@router.patch(
    "/{repository_id}/monitoring",
    response_model=RepositoryRead,
    summary="Toggle automated continuous PR monitoring for a repository",
)
async def update_repository_monitoring(
    repository_id: str,
    payload: RepositoryMonitoringUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> RepositoryRead:
    stmt = (
        select(Repository)
        .options(
            selectinload(Repository.pull_requests)
            .selectinload(PullRequest.review_jobs)
            .selectinload(ReviewJob.review_run)
        )
        .where(Repository.id == repository_id)
    )
    result = await db.execute(stmt)
    repo = result.scalars().first()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    repo.is_active = payload.is_active
    await db.commit()
    await db.refresh(repo)

    audit_repo = AuditRepository(db)
    await audit_repo.record(
        actor="dashboard-user",
        action="REPOSITORY_MONITORING_TOGGLED",
        resource_type="repository",
        resource_id=repo.id,
        metadata_payload={"is_active": repo.is_active},
    )

    pr_count = len(repo.pull_requests)
    review_count = sum(
        1 for pr in repo.pull_requests for job in pr.review_jobs if job.review_run is not None
    )

    return RepositoryRead(
        id=repo.id,
        github_repo_id=repo.github_repo_id,
        name=repo.name,
        owner=repo.owner,
        url=repo.url,
        default_branch=repo.default_branch,
        language=repo.language,
        is_active=repo.is_active,
        pull_requests_count=pr_count,
        reviews_count=review_count,
        last_reviewed_at=None,
        health_status="HEALTHY",
        created_at=repo.created_at,
        updated_at=repo.updated_at,
    )


@router.post(
    "/{repository_id}/sync",
    response_model=RepositorySyncResponse,
    summary="Synchronize recent open pull requests from GitHub for this repository",
)
async def sync_repository_pull_requests(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
) -> RepositorySyncResponse:
    stmt = select(Repository).where(Repository.id == repository_id)
    result = await db.execute(stmt)
    repo = result.scalars().first()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    synced_prs: List[PullRequestSummary] = []
    async with GitHubClient() as client:
        try:
            gh_prs = await client.list_pull_requests(repo.owner, repo.name, state="open", per_page=30)
            for p in gh_prs:
                pr_num = p.get("number")
                pr_id = p.get("id")
                if not pr_num or not pr_id:
                    continue

                pr_stmt = select(PullRequest).where(
                    PullRequest.repository_id == repo.id,
                    PullRequest.number == pr_num,
                )
                pr_res = await db.execute(pr_stmt)
                existing = pr_res.scalars().first()

                head_sha = p.get("head", {}).get("sha", "00000000")
                title = p.get("title", f"Pull Request #{pr_num}")
                author = p.get("user", {}).get("login", "unknown")
                source_branch = p.get("head", {}).get("ref", "feature")
                target_branch = p.get("base", {}).get("ref", repo.default_branch)

                if existing:
                    existing.title = title
                    existing.source_branch = source_branch
                    existing.target_branch = target_branch
                    existing.commit_sha = head_sha
                    existing.status = p.get("state", "OPEN").upper()
                    target_pr = existing
                else:
                    new_pr = PullRequest(
                        github_pr_id=pr_id,
                        repository_id=repo.id,
                        number=pr_num,
                        title=title,
                        author=author,
                        source_branch=source_branch,
                        target_branch=target_branch,
                        commit_sha=head_sha,
                        status=p.get("state", "OPEN").upper(),
                    )
                    db.add(new_pr)
                    target_pr = new_pr

                await db.commit()
                await db.refresh(target_pr)

                synced_prs.append(
                    PullRequestSummary(
                        id=target_pr.id,
                        number=target_pr.number,
                        title=target_pr.title,
                        author=target_pr.author,
                        source_branch=target_pr.source_branch,
                        target_branch=target_pr.target_branch,
                        commit_sha=target_pr.commit_sha,
                        status=target_pr.status,
                        created_at=target_pr.created_at,
                        updated_at=target_pr.updated_at,
                    )
                )

        except Exception as e:
            logger.warning(f"GitHub pull request sync returned error: {e}")
            raise ProblemDetailException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                title="GitHub Pull Request Sync Failed",
                detail=f"Failed to synchronize pull requests from GitHub: {str(e)}",
            )

    audit_repo = AuditRepository(db)
    await audit_repo.record(
        actor="dashboard-user",
        action="REPOSITORY_PULL_REQUESTS_SYNCED",
        resource_type="repository",
        resource_id=repo.id,
        metadata_payload={"synced_count": len(synced_prs)},
    )

    return RepositorySyncResponse(
        repository_id=repo.id,
        synced_pull_requests_count=len(synced_prs),
        pull_requests=synced_prs,
        message=f"Successfully synchronized {len(synced_prs)} pull requests from GitHub.",
    )


@router.delete(
    "/{repository_id}",
    status_code=status.HTTP_200_OK,
    summary="Disconnect and remove a repository from CodeGuardian AI",
)
async def delete_repository(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Repository).where(Repository.id == repository_id)
    result = await db.execute(stmt)
    repo = result.scalars().first()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    repo_name = f"{repo.owner}/{repo.name}"
    await db.delete(repo)
    await db.commit()

    audit_repo = AuditRepository(db)
    await audit_repo.record(
        actor="dashboard-user",
        action="REPOSITORY_DELETED",
        resource_type="repository",
        resource_id=repository_id,
        metadata_payload={"repository": repo_name},
    )

    return {
        "status": "DELETED",
        "repository_id": repository_id,
        "message": f"Repository '{repo_name}' successfully disconnected and removed from monitoring.",
    }


@router.get(
    "/{repository_id}",
    response_model=RepositoryDetail,
    summary="Get repository details by ID",
)
async def get_repository_detail(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
) -> RepositoryDetail:
    stmt = (
        select(Repository)
        .options(
            selectinload(Repository.pull_requests)
            .selectinload(PullRequest.review_jobs)
            .selectinload(ReviewJob.review_run)
        )
        .where(Repository.id == repository_id)
    )
    result = await db.execute(stmt)
    repo = result.scalars().first()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    prs_summary: List[PullRequestSummary] = []
    for pr in sorted(repo.pull_requests, key=lambda p: p.created_at, reverse=True):
        latest_run = None
        for job in pr.review_jobs:
            if job.review_run:
                latest_run = job.review_run
                break

        prs_summary.append(
            PullRequestSummary(
                id=pr.id,
                number=pr.number,
                title=pr.title,
                author=pr.author,
                source_branch=pr.source_branch,
                target_branch=pr.target_branch,
                commit_sha=pr.commit_sha,
                status=pr.status,
                latest_review_run_id=latest_run.id if latest_run else None,
                latest_risk_score=latest_run.risk_score if latest_run else None,
                latest_risk_grade=latest_run.risk_grade if latest_run else None,
                created_at=pr.created_at,
                updated_at=pr.updated_at,
            )
        )

    return RepositoryDetail(
        id=repo.id,
        github_repo_id=repo.github_repo_id,
        name=repo.name,
        owner=repo.owner,
        url=repo.url,
        default_branch=repo.default_branch,
        language=repo.language,
        is_active=repo.is_active,
        pull_requests_count=len(repo.pull_requests),
        reviews_count=sum(
            1 for pr in repo.pull_requests for job in pr.review_jobs if job.review_run is not None
        ),
        last_reviewed_at=prs_summary[0].created_at if prs_summary else None,
        health_status="HEALTHY",
        created_at=repo.created_at,
        updated_at=repo.updated_at,
        recent_pull_requests=prs_summary,
    )
