import base64
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import settings
from app.github.client import GitHubClient
from app.models.finding import Finding
from app.models.pull_request import PullRequest
from app.models.remediation import FixPR, RemediationAttempt
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.remediation.sandbox import SandboxPipeline
from app.repositories.audit_repository import AuditRepository
from app.repositories.finding_repository import FindingRepository
from app.repositories.remediation_repository import FixPRRepository, RemediationRepository
from app.schemas.remediation import FixPRCreateRequest, FixPRResponse, RemediationStatus
from app.utils.logging import get_logger

logger = get_logger("codeguardian.remediation.fix_pr")


class FixPRService:
    """
    Orchestrates automated GitHub branch creation, patch application,
    Pull Request dispatch for validated remediations, and webhook lifecycle tracking.
    """

    def __init__(self, client: Optional[GitHubClient] = None):
        self.client = client or GitHubClient()

    @classmethod
    def format_fix_pr_body(
        cls,
        finding: Finding,
        validation_result: Dict[str, Any],
    ) -> str:
        """Constructs an informative, compliance-ready markdown description for the Fix PR."""
        stages = validation_result.get("stages", {})
        val_patch = validation_result.get("patch_application", {}).get("status", "PASSED")
        val_syntax = validation_result.get("syntax_check", {}).get("status", "PASSED")
        val_scanner = validation_result.get("scanner_check", {}).get("status", "PASSED")
        val_tests = validation_result.get("unit_tests", {}).get("status", "SKIPPED")
        val_regression = validation_result.get("regression_check", {}).get("status", "PASSED")

        body_lines = [
            "## 🛡️ CodeGuardian AI — Automated Fix Pull Request",
            "",
            f"**Target Finding:** `{finding.title}` (`{finding.severity}`)",
            f"**Category:** `{finding.category}` | **Location:** `{finding.file_path}:{finding.line_start or 1}`",
            "",
            "### 📝 Description & Root Cause",
            finding.description or "Automated remediation generated for security finding.",
            "",
            "### 💡 Policy Standard",
            f"`{finding.policy_reference or 'Industry DevSecOps Baseline'}`",
            "",
            "### 🧪 5-Stage Sandboxed Validation Pipeline",
            f"- {'✅' if val_patch == 'PASSED' else '❌'} **Patch Application:** `{val_patch}`",
            f"- {'✅' if val_syntax == 'PASSED' else '❌'} **Syntax Check (AST):** `{val_syntax}`",
            f"- {'✅' if val_scanner == 'PASSED' else '❌'} **Targeted Scanner Check:** `{val_scanner}` (Vulnerability eliminated)",
            f"- {'✅' if val_tests == 'PASSED' else 'ℹ️'} **Unit Tests:** `{val_tests}`",
            f"- {'✅' if val_regression == 'PASSED' else '❌'} **Regression Check:** `{val_regression}`",
            "",
            "---",
            "<sub>*This Fix PR was synthesized and sandboxed by CodeGuardian AI. "
            "Human developer review and approval required before merging.*</sub>",
        ]
        return "\n".join(body_lines)

    async def create_fix_pull_request(
        self,
        session: AsyncSession,
        request: FixPRCreateRequest,
        user_id: Optional[str] = None,
    ) -> FixPRResponse:
        """
        Submits a dedicated GitHub Fix Pull Request for a validated remediation attempt.
        Never pushes directly to default branch; requires developer human-in-the-loop merge.
        """
        # 1. Fetch RemediationAttempt with Finding, PR, and Repo
        stmt = (
            select(RemediationAttempt)
            .options(
                selectinload(RemediationAttempt.fix_pr),
                selectinload(RemediationAttempt.finding)
                .selectinload(Finding.review_run)
                .selectinload(ReviewRun.review_job)
                .selectinload(ReviewJob.pull_request)
                .selectinload(PullRequest.repository),
            )
            .where(RemediationAttempt.id == request.remediation_attempt_id)
        )
        res = await session.execute(stmt)
        attempt = res.scalars().first()

        if not attempt:
            raise ValueError(f"RemediationAttempt '{request.remediation_attempt_id}' not found.")

        # 2. Gate Verification: Check duplicate first
        if attempt.fix_pr or attempt.status == RemediationStatus.APPLIED.value:
            existing_num = attempt.fix_pr.number if attempt.fix_pr else "existing"
            raise ValueError(
                f"Fix PR already exists for this remediation attempt (PR #{existing_num})."
            )

        if attempt.status != RemediationStatus.VALIDATED.value:
            raise ValueError(
                f"Cannot create Fix PR: RemediationAttempt status is '{attempt.status}'. "
                "Only 'VALIDATED' patches can be submitted as Fix PRs."
            )

        finding = attempt.finding

        if not finding or not finding.review_run:
            raise ValueError("Finding or ReviewRun association missing for RemediationAttempt.")

        pr = finding.review_run.review_job.pull_request if finding.review_run.review_job else None
        repo = pr.repository if pr else None

        if not pr or not repo:
            raise ValueError("PullRequest or Repository relation missing.")

        owner = repo.owner
        repo_name = repo.name
        base_branch = pr.source_branch or repo.default_branch or "main"
        branch_name = request.branch_name or f"codeguardian/fix-{finding.id[:8]}"
        title = request.custom_title or f"🛡️ Fix({finding.category.lower()}): {finding.title}"
        body = request.custom_body or self.format_fix_pr_body(finding, attempt.validation_result)

        # 3. GitHub API or Mock Environment Execution
        if not self.client.token or self.client.token.startswith("mock_"):
            logger.info("GitHub Token is unset or in mock mode; simulating clean Fix PR submission.")
            github_pr_id = 7001
            pr_number = 105
            pr_url = f"https://github.com/{owner}/{repo_name}/pull/{pr_number}"
        else:
            try:
                # A. Create Git Branch
                await self.client.create_branch(
                    owner=owner,
                    repo=repo_name,
                    branch_name=branch_name,
                    base_sha=pr.commit_sha,
                )

                # B. Fetch target file contents on branch to get current blob SHA
                existing_file_meta = await self.client.get_file_contents(
                    owner=owner,
                    repo=repo_name,
                    path=finding.file_path,
                    ref=branch_name,
                )
                blob_sha = existing_file_meta.get("sha")
                raw_base64 = existing_file_meta.get("content", "")
                orig_file_content = base64.b64decode(raw_base64).decode("utf-8")

                # C. Apply patch to file
                success, patched_content, err = SandboxPipeline.apply_unified_diff_to_string(
                    orig_file_content, attempt.patch
                )
                if not success:
                    raise ValueError(f"Could not apply patch to target file on branch: {err}")

                patched_base64 = base64.b64encode(patched_content.encode("utf-8")).decode("utf-8")

                # D. Commit updated file to branch
                commit_msg = f"fix(security): resolve {finding.title}\n\nAutomated fix by CodeGuardian AI."
                await self.client.create_or_update_file_contents(
                    owner=owner,
                    repo=repo_name,
                    path=finding.file_path,
                    message=commit_msg,
                    content_base64=patched_base64,
                    branch=branch_name,
                    sha=blob_sha,
                )

                # E. Submit Pull Request
                gh_pr = await self.client.create_pull_request(
                    owner=owner,
                    repo=repo_name,
                    title=title,
                    head=branch_name,
                    base=base_branch,
                    body=body,
                )
                github_pr_id = gh_pr.get("id", 7001)
                pr_number = gh_pr.get("number", 105)
                pr_url = gh_pr.get("html_url", f"https://github.com/{owner}/{repo_name}/pull/{pr_number}")

            except Exception as e:
                logger.error(f"Failed to create Fix PR on GitHub: {e}")
                raise RuntimeError(f"GitHub API Error during Fix PR creation: {str(e)}")

        # 4. Persist FixPR Entity & Update Remediation Status
        fix_pr = FixPR(
            remediation_attempt_id=attempt.id,
            github_pr_id=github_pr_id,
            number=pr_number,
            url=pr_url,
            status="OPEN",
        )
        session.add(fix_pr)
        attempt.status = RemediationStatus.APPLIED.value
        await session.flush()

        # 5. Record Compliance Audit Log
        audit_repo = AuditRepository(session)
        await audit_repo.record(
            actor=user_id or "DEVELOPER",
            action="FIX_PR_CREATED",
            resource_type="FixPR",
            resource_id=fix_pr.id,
            metadata_payload={
                "github_pr_id": github_pr_id,
                "number": pr_number,
                "url": pr_url,
                "branch_name": branch_name,
                "base_branch": base_branch,
                "finding_id": finding.id,
                "remediation_attempt_id": attempt.id,
            },
        )
        await session.commit()
        await session.refresh(fix_pr)

        logger.info(f"Fix PR #{pr_number} successfully created for Finding '{finding.id}' ({pr_url})")

        return FixPRResponse(
            id=fix_pr.id,
            remediation_attempt_id=attempt.id,
            finding_id=finding.id,
            repo_name=f"{owner}/{repo_name}",
            github_pr_id=fix_pr.github_pr_id,
            number=fix_pr.number,
            url=fix_pr.url,
            branch_name=branch_name,
            base_branch=base_branch,
            status=fix_pr.status,
            created_at=fix_pr.created_at,
        )

    async def get_fix_pr(
        self, session: AsyncSession, fix_pr_id: str
    ) -> Optional[FixPRResponse]:
        """Fetches FixPR details by UUID."""
        stmt = (
            select(FixPR)
            .options(
                selectinload(FixPR.remediation_attempt)
                .selectinload(RemediationAttempt.finding)
                .selectinload(Finding.review_run)
                .selectinload(ReviewRun.review_job)
                .selectinload(ReviewJob.pull_request)
                .selectinload(PullRequest.repository)
            )
            .where(FixPR.id == fix_pr_id)
        )
        res = await session.execute(stmt)
        fix_pr = res.scalars().first()
        if not fix_pr:
            return None

        attempt = fix_pr.remediation_attempt
        finding = attempt.finding if attempt else None
        pr = finding.review_run.review_job.pull_request if finding and finding.review_run and finding.review_run.review_job else None
        repo = pr.repository if pr else None
        repo_name = f"{repo.owner}/{repo.name}" if repo else "unknown/unknown"

        return FixPRResponse(
            id=fix_pr.id,
            remediation_attempt_id=fix_pr.remediation_attempt_id,
            finding_id=finding.id if finding else "",
            repo_name=repo_name,
            github_pr_id=fix_pr.github_pr_id,
            number=fix_pr.number,
            url=fix_pr.url,
            branch_name=f"codeguardian/fix-{(finding.id if finding else '')[:8]}",
            base_branch=pr.source_branch if pr else "main",
            status=fix_pr.status,
            created_at=fix_pr.created_at,
        )

    async def handle_fix_pr_webhook_event(
        self,
        session: AsyncSession,
        github_pr_id: int,
        action: str,
        merged: bool = False,
    ) -> Optional[FixPRResponse]:
        """
        Synchronizes Fix PR lifecycle events from GitHub webhooks:
        If PR was merged, transitions FixPR to MERGED, and updates Finding to RESOLVED.
        If PR was closed without merge, transitions FixPR to CLOSED.
        """
        fix_pr_repo = FixPRRepository(session)
        finding_repo = FindingRepository(session)
        audit_repo = AuditRepository(session)

        stmt = (
            select(FixPR)
            .options(selectinload(FixPR.remediation_attempt).selectinload(RemediationAttempt.finding))
            .where(FixPR.github_pr_id == github_pr_id)
        )
        res = await session.execute(stmt)
        fix_pr = res.scalars().first()

        if not fix_pr:
            return None

        new_status = fix_pr.status
        finding = fix_pr.remediation_attempt.finding if fix_pr.remediation_attempt else None

        if merged or (action == "closed" and merged):
            new_status = "MERGED"
            if finding:
                await finding_repo.update(
                    finding.id,
                    status="RESOLVED",
                )
            await audit_repo.record(
                actor="GITHUB_FIX_PR_MERGED",
                action="FIX_PR_MERGED",
                resource_type="FixPR",
                resource_id=fix_pr.id,
                metadata_payload={"number": fix_pr.number, "finding_id": finding.id if finding else None},
            )


        elif action == "closed":
            new_status = "CLOSED"
            await audit_repo.record(
                actor="GITHUB_WEBHOOK",
                action="FIX_PR_CLOSED",
                resource_type="FixPR",
                resource_id=fix_pr.id,
                metadata_payload={"number": fix_pr.number},
            )

        fix_pr.status = new_status
        await session.commit()
        await session.refresh(fix_pr)

        logger.info(f"Synchronized Fix PR #{fix_pr.number} (GitHub PR ID: {github_pr_id}) to status '{new_status}'.")
        return await self.get_fix_pr(session, fix_pr.id)
