import json
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from app.config.settings import settings
from app.github.security import (
    record_delivery_idempotency,
    sanitize_identifier,
    verify_hmac_signature,
)
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob
from app.repositories.audit_repository import AuditRepository
from app.repositories.pull_request_repository import PullRequestRepository
from app.repositories.repository_repository import RepositoryRepository
from app.repositories.review_repository import ReviewJobRepository
from app.schemas.errors import ProblemDetailException
from app.schemas.github import PullRequestWebhookPayload, WebhookResponse
from app.schemas.queue import ReviewJobPayload
from app.utils.logging import get_logger
from app.workers.queue import ReviewQueueInterface, get_review_queue

logger = get_logger("codeguardian.github.service")

# GitHub Pull Request actions that trigger automated static analysis and multi-agent review
ACTIONABLE_PR_ACTIONS = {"opened", "synchronize", "reopened"}


class GitHubWebhookService:
    """Orchestrates secure ingestion, verification, database persistence, and review job creation."""

    def __init__(
        self,
        session: AsyncSession,
        queue: Optional[ReviewQueueInterface] = None,
    ):
        self.session = session
        self.queue = queue or get_review_queue()
        self.repo_repository = RepositoryRepository(session)
        self.pr_repository = PullRequestRepository(session)
        self.review_job_repository = ReviewJobRepository(session)
        self.audit_repository = AuditRepository(session)

    async def process_webhook(
        self,
        raw_body: bytes,
        signature_header: Optional[str],
        event_type: Optional[str],
        delivery_id: Optional[str],
    ) -> WebhookResponse:
        """
        Validates HMAC, checks delivery idempotency, parses PR payload,
        persists repository and PR entities, and enqueues a ReviewJob.
        """
        # 1. Validate required headers presence
        if not event_type:
            raise ProblemDetailException(
                status_code=400,
                title="Bad Request",
                detail="Missing required header 'X-GitHub-Event'.",
                type_uri="https://errors.codeguardian.ai/v1/missing-header",
            )

        if not delivery_id:
            raise ProblemDetailException(
                status_code=400,
                title="Bad Request",
                detail="Missing required header 'X-GitHub-Delivery'.",
                type_uri="https://errors.codeguardian.ai/v1/missing-header",
            )

        if not signature_header:
            raise ProblemDetailException(
                status_code=401,
                title="Unauthorized",
                detail="Missing required header 'X-Hub-Signature-256'.",
                type_uri="https://errors.codeguardian.ai/v1/unauthorized",
            )

        # 2. Verify HMAC-SHA256 signature
        if not verify_hmac_signature(raw_body, signature_header, settings.GITHUB_WEBHOOK_SECRET):
            raise ProblemDetailException(
                status_code=401,
                title="Unauthorized",
                detail="HMAC signature verification failed. Invalid secret or payload altered.",
                type_uri="https://errors.codeguardian.ai/v1/invalid-signature",
            )

        # 3. Check and record delivery idempotency (Replay Defense)
        is_fresh_delivery = await record_delivery_idempotency(delivery_id)
        if not is_fresh_delivery:
            logger.warning("Duplicate webhook delivery rejected", extra={"delivery_id": delivery_id})
            raise ProblemDetailException(
                status_code=409,
                title="Conflict",
                detail=f"Duplicate delivery: Webhook delivery '{delivery_id}' has already been processed or is currently in flight.",
                type_uri="https://errors.codeguardian.ai/v1/duplicate-delivery",
            )

        # 4. Check supported event type
        if event_type != "pull_request":
            logger.info("Ignoring non-PR GitHub event", extra={"event": event_type, "delivery_id": delivery_id})
            raise ProblemDetailException(
                status_code=400,
                title="Bad Request",
                detail=f"Unsupported event type '{event_type}'. Only 'pull_request' events trigger reviews.",
                type_uri="https://errors.codeguardian.ai/v1/unsupported-event",
            )

        # 5. Parse and validate JSON payload
        try:
            payload_data = json.loads(raw_body.decode("utf-8"))
            payload = PullRequestWebhookPayload.model_validate(payload_data)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.error("Malformed JSON webhook payload", extra={"error": str(exc)})
            raise ProblemDetailException(
                status_code=400,
                title="Bad Request",
                detail="Malformed JSON in webhook request body.",
                type_uri="https://errors.codeguardian.ai/v1/malformed-payload",
            )
        except ValidationError as exc:
            logger.error("Pydantic validation failure on webhook payload", extra={"errors": exc.errors()})
            raise ProblemDetailException(
                status_code=400,
                title="Bad Request",
                detail=f"Invalid pull request webhook structure: {exc.errors()}",
                type_uri="https://errors.codeguardian.ai/v1/schema-validation-failed",
            )

        # 6. Sanitize untrusted identifiers (defense against path traversal / injection)
        try:
            sanitize_identifier(payload.repository.name, "repository.name")
            sanitize_identifier(payload.repository.owner.login, "repository.owner.login")
            sanitize_identifier(payload.pull_request.head.ref, "pull_request.head.ref")
            sanitize_identifier(payload.pull_request.base.ref, "pull_request.base.ref")
            sanitize_identifier(payload.pull_request.user.login, "pull_request.user.login")
        except ValueError as exc:
            logger.warning("Sanitization error on webhook identifiers", extra={"error": str(exc)})
            raise ProblemDetailException(
                status_code=400,
                title="Bad Request",
                detail=str(exc),
                type_uri="https://errors.codeguardian.ai/v1/security-violation",
            )

        # 7. Upsert Repository record
        repo_data = payload.repository
        repo = await self.repo_repository.get_by_github_repo_id(repo_data.id)
        if repo is None:
            repo = await self.repo_repository.create(
                github_repo_id=repo_data.id,
                name=repo_data.name,
                owner=repo_data.owner.login,
                url=repo_data.html_url,
                default_branch=repo_data.default_branch,
                language=repo_data.language,
                is_active=True,
            )
            logger.info("Registered new repository via webhook", extra={"repo": repo_data.full_name})
        else:
            repo = await self.repo_repository.update(
                repo.id,
                name=repo_data.name,
                owner=repo_data.owner.login,
                url=repo_data.html_url,
                default_branch=repo_data.default_branch,
                language=repo_data.language,
            )

        # 8. Upsert PullRequest record
        pr_data = payload.pull_request
        pr = await self.pr_repository.get_by_github_pr_id(pr_data.id)
        if pr is None:
            pr = await self.pr_repository.create(
                github_pr_id=pr_data.id,
                repository_id=repo.id,
                number=pr_data.number,
                title=pr_data.title,
                author=pr_data.user.login,
                source_branch=pr_data.head.ref,
                target_branch=pr_data.base.ref,
                commit_sha=pr_data.head.sha,
                status=pr_data.state.upper(),
            )
            logger.info("Tracked new pull request", extra={"pr": f"#{pr_data.number}", "repo": repo_data.full_name})
        else:
            pr = await self.pr_repository.update(
                pr.id,
                title=pr_data.title,
                source_branch=pr_data.head.ref,
                target_branch=pr_data.base.ref,
                commit_sha=pr_data.head.sha,
                status=pr_data.state.upper(),
            )

        # 8b. Synchronize Fix PR lifecycle state if this PR is a tracked FixPR
        try:
            from app.remediation.fix_pr import FixPRService
            fix_pr_svc = FixPRService()
            await fix_pr_svc.handle_fix_pr_webhook_event(
                session=self.session,
                github_pr_id=pr_data.id,
                action=payload.action.lower(),
                merged=bool(getattr(pr_data, "merged", False)),
            )
        except Exception as f_err:
            logger.debug(f"FixPR webhook event check skipped: {f_err}")

        # 9. Check if action requires review execution
        action = payload.action.lower()

        if action not in ACTIONABLE_PR_ACTIONS:
            logger.info(
                f"PR action '{action}' is non-actionable; skipping review job creation",
                extra={"pr": pr.number, "action": action},
            )
            await self.audit_repository.record(
                actor=payload.sender.login if payload.sender else pr_data.user.login,
                action="PULL_REQUEST_WEBHOOK_IGNORED",
                resource_type="pull_request",
                resource_id=pr.id,
                metadata_payload={
                    "delivery_id": delivery_id,
                    "action": action,
                    "reason": f"Action '{action}' does not trigger automated review",
                },
            )
            return WebhookResponse(
                status="ignored",
                job_id=None,
                delivery_id=delivery_id,
                event=event_type,
                action=action,
                message=f"Action '{action}' acknowledged but does not trigger automated review.",
            )

        # 10. Create ReviewJob entity (status=QUEUED)
        job = await self.review_job_repository.create(
            pull_request_id=pr.id,
            status="QUEUED",
        )

        # 11. Record immutable compliance audit log
        await self.audit_repository.record(
            actor=payload.sender.login if payload.sender else pr_data.user.login,
            action="REVIEW_JOB_ENQUEUED",
            resource_type="review_job",
            resource_id=job.id,
            metadata_payload={
                "delivery_id": delivery_id,
                "repository": f"{repo.owner}/{repo.name}",
                "pr_number": pr.number,
                "commit_sha": pr.commit_sha,
                "action": action,
            },
        )

        # 12. Dispatch job payload to review queue for asynchronous worker consumption
        job_payload = ReviewJobPayload(
            job_id=job.id,
            pull_request_id=pr.id,
            repo_name=repo.name,
            repo_owner=repo.owner,
            pr_number=pr.number,
            commit_sha=pr.commit_sha,
            action=action,
        )
        try:
            await self.queue.enqueue_review(job_payload)
        except Exception as exc:
            logger.warning(
                "Failed to dispatch job to queue broker; job remains recorded as QUEUED in database",
                extra={"job_id": job.id, "error": str(exc)},
            )

        logger.info(
            "Enqueued automated review job",
            extra={
                "job_id": job.id,
                "repo": f"{repo.owner}/{repo.name}",
                "pr_number": pr.number,
                "commit_sha": pr.commit_sha[:8],
            },
        )

        return WebhookResponse(
            status="enqueued",
            job_id=job.id,
            delivery_id=delivery_id,
            event=event_type,
            action=action,
        )
