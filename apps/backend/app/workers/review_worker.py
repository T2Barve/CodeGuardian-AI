import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.session import async_session_maker
from app.findings.engine import FindingEngine
from app.findings.service import FindingService
from app.risk.service import RiskService
from app.models.review import ReviewJob, ReviewRun
from app.repositories.audit_repository import AuditRepository
from app.repositories.pull_request_repository import PullRequestRepository
from app.repositories.review_repository import ReviewJobRepository, ReviewRunRepository
from app.agents.service import SupervisorService
from app.agents.state import ReviewStateInput
from app.scanners.runner import ScannerEngine
from app.schemas.queue import ReviewJobPayload
from app.utils.logging import get_logger
from app.workers.queue import ReviewQueueInterface, get_review_queue

logger = get_logger("codeguardian.worker.engine")


class ReviewWorker:
    """
    Background review worker daemon responsible for dequeuing jobs,
    managing ReviewJob state transitions, driving analysis, and routing retries/DLQs.
    """

    def __init__(
        self,
        queue: Optional[ReviewQueueInterface] = None,
        session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
        execution_handler: Optional[Callable[[ReviewJobPayload, AsyncSession], Any]] = None,
        scanner_engine: Optional[ScannerEngine] = None,
        finding_engine: Optional[FindingEngine] = None,
        supervisor_service: Optional[SupervisorService] = None,
    ):
        self.queue = queue or get_review_queue()
        self.session_factory = session_factory or async_session_maker
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.execution_handler = execution_handler
        self.scanner_engine = scanner_engine or ScannerEngine()
        self.finding_engine = finding_engine or FindingEngine()
        self.supervisor_service = supervisor_service or SupervisorService()
        self.running = True

    def stop(self) -> None:
        """Signals the worker loop to stop after finishing the current job."""
        self.running = False

    async def process_job(self, payload: ReviewJobPayload) -> bool:
        """
        Executes complete lifecycle for a dequeued review job:
          QUEUED -> RUNNING -> (COMPLETED | RETRYING | FAILED/DLQ)
        """
        start_time = time.perf_counter()
        job_id = payload.job_id
        logger.info(
            "Worker beginning processing for job",
            extra={"job_id": job_id, "pr": payload.pr_number, "repo": payload.repo_name},
        )

        # 1. Inspect and transition ReviewJob state to RUNNING in database
        async with self.session_factory() as session:
            job_repo = ReviewJobRepository(session)
            run_repo = ReviewRunRepository(session)
            audit_repo = AuditRepository(session)

            job = await job_repo.get(job_id)
            if not job:
                logger.error("Job not found in database; acknowledging and skipping", extra={"job_id": job_id})
                await self.queue.ack_review(payload)
                return False

            if job.status == "COMPLETED":
                logger.info("Job already completed in DB; acknowledging duplicate", extra={"job_id": job_id})
                await self.queue.ack_review(payload)
                return True

            # Mark RUNNING
            await job_repo.update(
                job_id,
                status="RUNNING",
                started_at=datetime.now(timezone.utc),
            )

            # Ensure ReviewRun record exists
            review_run = await run_repo.get_by_job_id(job_id)
            if not review_run:
                review_run = await run_repo.create(
                    review_job_id=job_id,
                    status="RUNNING",
                    configuration={
                        "commit_sha": payload.commit_sha,
                        "pr_number": payload.pr_number,
                        "repo_name": payload.repo_name,
                    },
                )
            else:
                await run_repo.update(review_run.id, status="RUNNING")

            # Audit transition
            await audit_repo.record(
                actor="codeguardian-worker",
                action="REVIEW_JOB_STARTED",
                resource_type="review_job",
                resource_id=job_id,
                metadata_payload={
                    "commit_sha": payload.commit_sha,
                    "retry_count": payload.retry_count,
                },
            )
            await session.commit()

        # 2. Execute review pipeline logic
        findings_count = 0
        try:
            async with self.session_factory() as session:
                if self.execution_handler:
                    await self.execution_handler(payload, session)
                elif payload.metadata and payload.metadata.get("workspace_path"):
                    workspace_dir = payload.metadata["workspace_path"]
                    changed_files = payload.metadata.get("changed_files")
                    raw_results, summaries = await self.scanner_engine.scan_repository(
                        workspace_dir, changed_files=changed_files
                    )
                    run_repo = ReviewRunRepository(session)
                    review_run = await run_repo.get_by_job_id(job_id)
                    if review_run:
                        normalized_scans = [
                            r.model_dump() if hasattr(r, "model_dump") else (r.to_dict() if hasattr(r, "to_dict") else r)
                            for r in raw_results
                        ]
                        input_data = ReviewStateInput(
                            repo_owner=payload.repo_name.split("/")[0] if "/" in payload.repo_name else "owner",
                            repo_name=payload.repo_name,
                            pr_number=payload.pr_number,
                            commit_sha=payload.commit_sha,
                            changed_files=changed_files or [],
                            diff_content=payload.metadata.get("diff_content", ""),
                            workspace_path=workspace_dir,
                            review_run_id=review_run.id,
                            normalized_scan_results=normalized_scans,
                        )
                        final_state = await self.supervisor_service.run_review(input_data=input_data, session=session)
                        correlated = final_state.get("correlated_findings", [])
                        persisted = await FindingService.persist_findings(
                            session=session,
                            review_run_id=review_run.id,
                            correlated_findings=correlated,
                        )
                        findings_count = len(persisted)
                        # Assess and persist deterministic risk score
                        lines_changed = payload.metadata.get("lines_changed")
                        files_changed = payload.metadata.get("files_changed")
                        await RiskService.assess_and_persist_review_risk(
                            session=session,
                            review_run_id=review_run.id,
                            lines_changed=lines_changed,
                            files_changed=files_changed,
                        )
                        # Phase 11: Synthesize and persist comprehensive review report
                        from app.reports.service import ReportService
                        report_service = ReportService()
                        await report_service.generate_and_persist_report(
                            session=session,
                            review_run_id=review_run.id,
                        )
                        # Phase 13: Publish Check Run and PR review comment to GitHub
                        try:
                            from app.github.reporter import GitHubReporter
                            reporter = GitHubReporter()
                            await reporter.publish_review_report(
                                session=session,
                                review_run_id=review_run.id,
                            )
                        except Exception as gh_err:
                            logger.warning(
                                f"GitHub review reporting skipped or non-critical: {gh_err}"
                            )
                elif payload.repo_owner and payload.repo_name and payload.pr_number:
                    import os
                    import tempfile
                    from app.github.client import GitHubClient

                    async with GitHubClient() as gh_client:
                        try:
                            pr_files = await gh_client.get_pull_request_files(
                                payload.repo_owner, payload.repo_name, payload.pr_number
                            )
                            diff_content = await gh_client.get_pull_request_diff(
                                payload.repo_owner, payload.repo_name, payload.pr_number
                            )
                        except Exception as gh_fetch_err:
                            logger.warning(f"Live GitHub PR fetch failed or offline: {gh_fetch_err}")
                            pr_files = []
                            diff_content = ""

                    changed_files = [f.get("filename") for f in pr_files if f.get("filename")]
                    lines_changed = sum(f.get("additions", 0) + f.get("deletions", 0) for f in pr_files)
                    files_changed = len(changed_files)

                    with tempfile.TemporaryDirectory(prefix="codeguardian_pr_") as temp_workspace:
                        # Write changed file snippets safely into temp_workspace
                        for f_info in pr_files:
                            fname = f_info.get("filename", "")
                            if ".." in fname or fname.startswith("/") or fname.startswith("\\"):
                                continue
                            file_path = os.path.join(temp_workspace, fname)
                            os.makedirs(os.path.dirname(file_path), exist_ok=True)
                            patch = f_info.get("patch", "")
                            if patch:
                                code_lines = [
                                    line[1:] for line in patch.splitlines()
                                    if line.startswith("+") and not line.startswith("+++")
                                ]
                                with open(file_path, "w", encoding="utf-8", errors="ignore") as f_out:
                                    f_out.write("\n".join(code_lines))

                        raw_results, summaries = await self.scanner_engine.scan_repository(
                            temp_workspace, changed_files=changed_files
                        )

                        run_repo = ReviewRunRepository(session)
                        review_run = await run_repo.get_by_job_id(job_id)
                        if review_run:
                            normalized_scans = [
                                r.model_dump() if hasattr(r, "model_dump") else (r.to_dict() if hasattr(r, "to_dict") else r)
                                for r in raw_results
                            ]
                            input_data = ReviewStateInput(
                                repo_owner=payload.repo_owner,
                                repo_name=payload.repo_name,
                                pr_number=payload.pr_number,
                                commit_sha=payload.commit_sha,
                                changed_files=changed_files,
                                diff_content=diff_content,
                                workspace_path=temp_workspace,
                                review_run_id=review_run.id,
                                normalized_scan_results=normalized_scans,
                            )
                            final_state = await self.supervisor_service.run_review(input_data=input_data, session=session)
                            correlated = final_state.get("correlated_findings", [])
                            persisted = await FindingService.persist_findings(
                                session=session,
                                review_run_id=review_run.id,
                                correlated_findings=correlated,
                            )
                            findings_count = len(persisted)
                            await RiskService.assess_and_persist_review_risk(
                                session=session,
                                review_run_id=review_run.id,
                                lines_changed=lines_changed,
                                files_changed=files_changed,
                            )
                            from app.reports.service import ReportService
                            report_service = ReportService()
                            await report_service.generate_and_persist_report(
                                session=session,
                                review_run_id=review_run.id,
                            )
                            try:
                                from app.github.reporter import GitHubReporter
                                reporter = GitHubReporter()
                                await reporter.publish_review_report(
                                    session=session,
                                    review_run_id=review_run.id,
                                )
                            except Exception as gh_err:
                                logger.debug(f"GitHub review reporting skipped: {gh_err}")
                else:
                    # Baseline Phase 4 processing execution: simulate initial checks
                    await asyncio.sleep(0.01)

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # 3. Transition to COMPLETED on success
            async with self.session_factory() as session:
                job_repo = ReviewJobRepository(session)
                run_repo = ReviewRunRepository(session)
                audit_repo = AuditRepository(session)

                await job_repo.update(
                    job_id,
                    status="COMPLETED",
                    completed_at=datetime.now(timezone.utc),
                )
                review_run = await run_repo.get_by_job_id(job_id)
                if review_run:
                    risk_info = (
                        f" | Grade {review_run.risk_grade} (Risk Score: {review_run.risk_score})"
                        if review_run.risk_score is not None
                        else ""
                    )
                    summary_text = (
                        f"Automated review job processed successfully in {duration_ms}ms with {findings_count} findings synthesized{risk_info}."
                        if findings_count > 0
                        else f"Automated review job processed successfully in {duration_ms}ms{risk_info}."
                    )
                    await run_repo.update(
                        review_run.id,
                        status="SUCCESS",
                        completed_at=datetime.now(timezone.utc),
                        duration_ms=duration_ms,
                        summary=summary_text,
                    )

                await audit_repo.record(
                    actor="codeguardian-worker",
                    action="REVIEW_JOB_COMPLETED",
                    resource_type="review_job",
                    resource_id=job_id,
                    metadata_payload={
                        "duration_ms": duration_ms,
                        "findings_count": findings_count,
                    },
                )
                await session.commit()

            # Acknowledge and clear from in-flight queue
            await self.queue.ack_review(payload)
            logger.info("Job processed and marked COMPLETED", extra={"job_id": job_id, "duration_ms": duration_ms})
            return True

        except Exception as exc:
            error_msg = str(exc)
            logger.error("Job processing failed with exception", extra={"job_id": job_id, "error": error_msg}, exc_info=True)

            # 4. Handle Failure: Retry or Dead-Letter Queue
            is_exhausted = (payload.retry_count + 1) >= self.max_retries

            async with self.session_factory() as session:
                job_repo = ReviewJobRepository(session)
                run_repo = ReviewRunRepository(session)
                audit_repo = AuditRepository(session)

                if not is_exhausted:
                    # Update status to RETRYING
                    await job_repo.update(
                        job_id,
                        status="RETRYING",
                        retry_count=payload.retry_count + 1,
                        error_message=f"Transient failure: {error_msg}",
                    )
                    await audit_repo.record(
                        actor="codeguardian-worker",
                        action="REVIEW_JOB_RETRYING",
                        resource_type="review_job",
                        resource_id=job_id,
                        metadata_payload={
                            "retry_attempt": payload.retry_count + 1,
                            "error": error_msg,
                        },
                    )
                else:
                    # Exhausted max retries: mark FAILED and record DLQ routing
                    await job_repo.update(
                        job_id,
                        status="FAILED",
                        retry_count=payload.retry_count + 1,
                        completed_at=datetime.now(timezone.utc),
                        error_message=f"Permanent failure (retries exhausted): {error_msg}",
                    )
                    review_run = await run_repo.get_by_job_id(job_id)
                    if review_run:
                        await run_repo.update(
                            review_run.id,
                            status="FAILED",
                            completed_at=datetime.now(timezone.utc),
                            summary=f"Review job failed permanently: {error_msg}",
                        )

                    await audit_repo.record(
                        actor="codeguardian-worker",
                        action="REVIEW_JOB_FAILED_DLQ",
                        resource_type="review_job",
                        resource_id=job_id,
                        metadata_payload={
                            "retries_exhausted": payload.retry_count + 1,
                            "error": error_msg,
                        },
                    )

                await session.commit()

            # Nack job in queue (either re-enqueue or route to DLQ)
            await self.queue.nack_review(
                payload=payload,
                error_message=error_msg,
                max_retries=self.max_retries,
                backoff_seconds=self.retry_backoff_seconds if not is_exhausted else 0.0,
            )
            return False

    async def run_once(self, timeout: int = 1) -> Optional[bool]:
        """Dequeues and processes a single review job. Returns None if no job available."""
        payload = await self.queue.dequeue_review(timeout=timeout)
        if not payload:
            return None
        return await self.process_job(payload)

    async def run_loop(self, max_jobs: Optional[int] = None) -> int:
        """
        Runs the continuous worker polling loop.
        Can be bounded by max_jobs (useful for integration tests and batch runs).
        """
        processed_count = 0
        logger.info("Worker polling loop active...")

        while self.running:
            try:
                result = await self.run_once(timeout=1)
                if result is not None:
                    processed_count += 1
                    if max_jobs is not None and processed_count >= max_jobs:
                        break
            except asyncio.CancelledError:
                logger.info("Worker run loop cancelled")
                break
            except Exception as exc:
                logger.error("Unexpected error in worker loop", extra={"error": str(exc)})
                await asyncio.sleep(0.5)

        logger.info("Worker loop exiting", extra={"processed_count": processed_count})
        return processed_count
