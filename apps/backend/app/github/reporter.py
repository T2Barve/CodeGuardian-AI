from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config.settings import settings
from app.github.client import GitHubClient, GitHubAPIError
from app.models.finding import Finding
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.reports.service import ReportService
from app.repositories.audit_repository import AuditRepository
from app.schemas.github import GitHubPublishResult, GitHubReportPreview
from app.schemas.report import ReviewReport
from app.schemas.risk import RiskGrade
from app.utils.logging import get_logger

logger = get_logger("codeguardian.github.reporter")

COMMENT_MARKER_PREFIX = "<!-- codeguardian-pr-review-summary:pr-"


class GitHubReporter:
    """
    Publishes automated DevSecOps Pull Request Check Runs, line annotations,
    and concise review summary comments with strict anti-spam deduplication.
    """

    def __init__(self, client: Optional[GitHubClient] = None):
        self.client = client or GitHubClient()
        self.report_service = ReportService()

    @classmethod
    def generate_comment_marker(cls, pr_number: int) -> str:
        """Returns deterministic HTML comment marker for anti-spam detection."""
        return f"{COMMENT_MARKER_PREFIX}{pr_number} -->"

    @classmethod
    def format_pr_review_comment(cls, report: ReviewReport) -> str:
        """
        Formats a concise, developer-friendly, and executive-ready GitHub PR comment.
        Includes marker tag at the top to prevent comment spam.
        """
        s = report.summary
        cb = report.category_breakdown
        marker = cls.generate_comment_marker(s.pr_number)

        grade_emojis = {
            RiskGrade.A: "🟢 **GRADE A** (Minimal Risk — Approved)",
            RiskGrade.B: "🔵 **GRADE B** (Low Risk — Minor Findings)",
            RiskGrade.C: "🟡 **GRADE C** (Moderate Risk — Attention Recommended)",
            RiskGrade.D: "🟠 **GRADE D** (Elevated Risk — Action Required)",
            RiskGrade.F: "🔴 **GRADE F** (Critical Risk — Merge BLOCKED)",
        }
        grade_text = grade_emojis.get(s.risk_grade, f"**GRADE {s.risk_grade.value}**")
        merge_badge = "✅ **MERGEABLE**" if s.is_mergeable else "🚫 **MERGE BLOCKED (Remediation Required)**"

        lines: List[str] = [
            marker,
            "## 🛡️ CodeGuardian AI — Pull Request DevSecOps Review",
            "",
            f"**Commit:** `{s.commit_sha[:8]}` | **Risk Score:** `{s.risk_score:.1f}/100` | **Status:** {merge_badge}",
            f"**Assessment:** {grade_text} | **Recommended Action:** `{s.recommended_action}`",
            "",
            "### 📊 Findings Distribution",
            "| Total | 🔴 Critical | 🟠 High | 🟡 Medium | 🔵 Low | ⚪ Info |",
            "| :---: | :---: | :---: | :---: | :---: | :---: |",
            f"| **{s.total_findings}** | **{s.critical_count}** | **{s.high_count}** | **{s.medium_count}** | **{s.low_count}** | **{s.info_count}** |",
            "",
            "### 🎯 Category Risk Radar",
            f"- 🛡️ **Security:** `{cb.security:.1f}/100`",
            f"- 💎 **Quality:** `{cb.quality:.1f}/100`",
            f"- 🧪 **Testing:** `{cb.testing:.1f}/100`",
            f"- 📚 **Documentation:** `{cb.documentation:.1f}/100`",
            f"- 📦 **Dependencies:** `{cb.dependency:.1f}/100`",
            "",
        ]

        if report.risk_driving_factors:
            lines.append("### ⚠️ Key Risk Driving Factors")
            for factor in report.risk_driving_factors:
                lines.append(f"- {factor}")
            lines.append("")

        # Highlight Top Critical & High Findings
        severe_findings = [f for f in report.findings if f.severity.upper() in ["CRITICAL", "HIGH"]]
        if severe_findings:
            lines.append(f"### 🚨 Severe Findings Requiring Action ({len(severe_findings)})")
            lines.append("| Severity | Finding | File & Location | Recommendation |")
            lines.append("| :---: | :--- | :--- | :--- |")
            for f in severe_findings[:8]:
                sev_icon = "🔴" if f.severity.upper() == "CRITICAL" else "🟠"
                loc = f"`{f.file_path}:{f.line_start or 1}`"
                rec = f.recommendation or f.description
                rec_snippet = rec[:80] + "..." if len(rec) > 80 else rec
                lines.append(f"| {sev_icon} **{f.severity}** | {f.title} | {loc} | {rec_snippet} |")
            lines.append("")

        lines.extend([
            "---",
            f"<sub>*Evaluated in `{s.duration_ms}ms` by LangGraph Supervisor and Specialist Agents grounded in ChromaDB policy standards.*</sub>",
            f"<sub>*View full telemetry, code snippets, and automated fixes in the [CodeGuardian Dashboard]({settings.BACKEND_CORS_ORIGINS[0] if getattr(settings, 'BACKEND_CORS_ORIGINS', None) else 'http://localhost:5173'}).*</sub>",
        ])

        return "\n".join(lines)

    @classmethod
    def build_check_run_annotations(cls, findings: List[Finding]) -> List[Dict[str, Any]]:
        """Converts findings into GitHub Check Run line-level annotations (max 50)."""
        annotations: List[Dict[str, Any]] = []

        # Sort by severity priority: CRITICAL first, then HIGH, then MEDIUM, LOW, INFO
        sev_priority = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        sorted_findings = sorted(
            findings,
            key=lambda f: sev_priority.get(f.severity.upper(), 5),
        )

        for f in sorted_findings[:50]:
            sev = f.severity.upper()
            if sev == "CRITICAL":
                level = "failure"
            elif sev in ["HIGH", "MEDIUM"]:
                level = "warning"
            else:
                level = "notice"

            start_line = f.line_start if f.line_start and f.line_start > 0 else 1
            end_line = f.line_end if f.line_end and f.line_end >= start_line else start_line

            msg = f"{f.description}\n\nRecommendation: {f.recommendation or 'Inspect code.'}"
            if f.policy_reference:
                msg += f"\nPolicy Citation: {f.policy_reference}"

            annotations.append({
                "path": f.file_path,
                "start_line": start_line,
                "end_line": end_line,
                "annotation_level": level,
                "title": f"[{sev}] {f.title}",
                "message": msg,
                "raw_details": f"Fingerprint: {f.fingerprint} | Category: {f.category}",
            })

        return annotations

    async def publish_check_run(
        self,
        owner: str,
        repo: str,
        report: ReviewReport,
    ) -> Dict[str, Any]:
        """Creates a completed Check Run on GitHub with conclusion and annotations."""
        s = report.summary

        # Determine Check Run conclusion
        if not s.is_mergeable or s.critical_count > 0 or s.risk_grade == RiskGrade.F:
            conclusion = "failure"
        elif s.high_count > 0 or s.risk_grade in [RiskGrade.D, RiskGrade.C]:
            conclusion = "neutral"
        else:
            conclusion = "success"

        annotations = self.build_check_run_annotations(report.findings)

        title = f"CodeGuardian: GRADE {s.risk_grade.value} ({s.risk_score:.1f}/100) — {s.recommended_action}"
        summary_text = (
            f"### CodeGuardian AI Automated Pull Request Review\n"
            f"- **Overall Risk:** `{s.risk_score:.1f}/100` ({s.risk_grade.value})\n"
            f"- **Gate Status:** {'MERGEABLE' if s.is_mergeable else 'BLOCKED'}\n"
            f"- **Findings:** {s.total_findings} total ({s.critical_count} critical, {s.high_count} high)\n"
            f"- **Duration:** {s.duration_ms}ms\n"
        )

        output_payload = {
            "title": title,
            "summary": summary_text,
            "text": report.markdown_content or summary_text,
            "annotations": annotations,
        }

        logger.info(
            f"Submitting GitHub Check Run on {owner}/{repo}@{s.commit_sha[:8]} "
            f"(Conclusion: {conclusion}, Annotations: {len(annotations)})"
        )

        return await self.client.create_check_run(
            owner=owner,
            repo=repo,
            name="CodeGuardian AI / DevSecOps Review",
            head_sha=s.commit_sha,
            status="completed",
            conclusion=conclusion,
            output=output_payload,
        )

    async def publish_or_update_pr_comment(
        self,
        owner: str,
        repo: str,
        report: ReviewReport,
    ) -> Dict[str, Any]:
        """
        Posts or updates the PR summary comment with anti-spam deduplication.
        If a comment with the marker tag exists, updates in place; otherwise creates a new one.
        """
        pr_number = report.summary.pr_number
        comment_body = self.format_pr_review_comment(report)
        marker = self.generate_comment_marker(pr_number)

        # 1. Search for existing CodeGuardian review comment on this PR
        existing_comments = await self.client.list_issue_comments(owner, repo, pr_number)
        matching_comment = None
        for c in existing_comments:
            body = c.get("body", "")
            if marker in body or COMMENT_MARKER_PREFIX in body:
                matching_comment = c
                break

        if matching_comment:
            comment_id = matching_comment["id"]
            logger.info(
                f"Existing review comment found on PR #{pr_number} (ID: {comment_id}); "
                f"updating in-place to prevent comment spam."
            )
            updated = await self.client.update_issue_comment(owner, repo, comment_id, comment_body)
            return {"action": "UPDATED", "comment_id": comment_id, "data": updated}

        # 2. If no existing comment found, create a new one
        logger.info(f"No existing review comment found on PR #{pr_number}; creating initial review comment.")
        created = await self.client.create_issue_comment(owner, repo, pr_number, comment_body)
        return {"action": "CREATED", "comment_id": created.get("id"), "data": created}

    async def publish_inline_comments(
        self,
        owner: str,
        repo: str,
        report: ReviewReport,
    ) -> int:
        """
        Posts inline review comments on changed lines for CRITICAL findings.
        Returns the number of successfully posted comments.
        """
        s = report.summary
        critical_findings = [f for f in report.findings if f.severity.upper() == "CRITICAL" and f.line_start]

        posted_count = 0
        for f in critical_findings[:5]:  # Limit to top 5 critical inline comments to avoid noise
            inline_body = (
                f"🚨 **CodeGuardian AI — [CRITICAL] {f.title}**\n\n"
                f"{f.description}\n\n"
                f"💡 **Recommendation:** {f.recommendation or 'Please review input validation.'}\n"
            )
            if f.policy_reference:
                inline_body += f"\n📜 **Policy Standard:** `{f.policy_reference}`"

            try:
                await self.client.create_pull_request_review_comment(
                    owner=owner,
                    repo=repo,
                    pull_number=s.pr_number,
                    body=inline_body,
                    commit_id=s.commit_sha,
                    path=f.file_path,
                    line=f.line_start or 1,
                )
                posted_count += 1
            except Exception as e:
                # GitHub may reject inline comment if the line was not modified in this PR diff
                logger.warning(
                    f"Could not post inline comment on {f.file_path}:{f.line_start} (likely outside PR diff): {e}"
                )

        return posted_count

    async def publish_review_report(
        self,
        session: AsyncSession,
        review_run_id: str,
    ) -> GitHubPublishResult:
        """
        Master orchestration method for Phase 13.
        Generates/fetches the review report, posts Check Run with annotations,
        posts/updates PR comment, and records audit trail.
        """
        # 1. Fetch ReviewRun with PR and Repository
        stmt = (
            select(ReviewRun)
            .options(
                selectinload(ReviewRun.review_job)
                .selectinload(ReviewJob.pull_request)
                .selectinload(PullRequest.repository)
            )
            .where(ReviewRun.id == review_run_id)
        )
        res = await session.execute(stmt)
        review_run = res.scalars().first()

        if not review_run:
            raise ValueError(f"ReviewRun '{review_run_id}' not found.")

        pr = review_run.review_job.pull_request if review_run.review_job else None
        repo = pr.repository if pr else None

        if not pr or not repo:
            raise ValueError(f"PullRequest or Repository relation missing for ReviewRun '{review_run_id}'.")

        # 2. Get or generate complete ReviewReport
        report = await self.report_service.get_report(session, review_run_id)
        if not report:
            report = await self.report_service.generate_and_persist_report(session, review_run_id)

        # 3. Check for GitHub Token / Mock Environment
        if not self.client.token or self.client.token.startswith("mock_"):
            logger.info("GitHub Token is unset or in mock mode; simulating clean GitHub reporting.")
            result = GitHubPublishResult(
                review_run_id=review_run_id,
                repo_name=repo.name,
                pr_number=pr.number,
                commit_sha=pr.commit_sha,
                check_run_id=1001,
                check_run_status="completed",
                check_run_conclusion="failure" if not report.summary.is_mergeable else "success",
                comment_id=2001,
                comment_action="CREATED",
                annotations_count=min(len(report.findings), 50),
                inline_comments_count=1 if any(f.severity.upper() == "CRITICAL" for f in report.findings) else 0,
                status="PUBLISHED",
                details="Mock delivery: Check run and PR comment simulated cleanly.",
            )
            return result

        # 4. Live GitHub API Publishing
        try:
            # A. Publish Check Run
            check_run_resp = await self.publish_check_run(repo.owner, repo.name, report)
            check_run_id = check_run_resp.get("id")

            # B. Publish or Update PR Comment (Anti-Spam)
            comment_resp = await self.publish_or_update_pr_comment(repo.owner, repo.name, report)
            comment_id = comment_resp.get("comment_id")
            comment_action = comment_resp.get("action", "CREATED")

            # C. Inline comments for Critical findings
            inline_count = await self.publish_inline_comments(repo.owner, repo.name, report)

            # D. Audit Log
            audit_repo = AuditRepository(session)
            await audit_repo.record(
                actor="SYSTEM_GITHUB_REPORTER",
                action="GITHUB_REVIEW_REPORT_PUBLISHED",
                resource_type="ReviewRun",
                resource_id=review_run.id,
                metadata_payload={
                    "check_run_id": check_run_id,
                    "comment_id": comment_id,
                    "comment_action": comment_action,
                    "conclusion": check_run_resp.get("conclusion"),
                    "risk_score": report.summary.risk_score,
                    "risk_grade": report.summary.risk_grade.value,
                    "is_mergeable": report.summary.is_mergeable,
                },
            )
            await session.commit()

            return GitHubPublishResult(
                review_run_id=review_run_id,
                repo_name=repo.name,
                pr_number=pr.number,
                commit_sha=pr.commit_sha,
                check_run_id=check_run_id,
                check_run_status="completed",
                check_run_conclusion=check_run_resp.get("conclusion", "success"),
                comment_id=comment_id,
                comment_action=comment_action,
                annotations_count=len(report.findings),
                inline_comments_count=inline_count,
                status="PUBLISHED",
                details=f"Check run #{check_run_id} and comment #{comment_id} ({comment_action}) published.",
            )

        except Exception as e:
            logger.error(f"Failed to publish review to GitHub for ReviewRun '{review_run_id}': {e}")
            return GitHubPublishResult(
                review_run_id=review_run_id,
                repo_name=repo.name,
                pr_number=pr.number,
                commit_sha=pr.commit_sha,
                check_run_status="failed",
                check_run_conclusion="neutral",
                status="FAILED",
                details=f"GitHub API Error: {str(e)}",
            )

    async def preview_github_report(
        self,
        session: AsyncSession,
        review_run_id: str,
    ) -> GitHubReportPreview:
        """
        Generates a dry-run preview of the PR review comment and Check Run annotations
        without publishing anything to GitHub.
        """
        stmt = (
            select(ReviewRun)
            .options(
                selectinload(ReviewRun.review_job)
                .selectinload(ReviewJob.pull_request)
                .selectinload(PullRequest.repository)
            )
            .where(ReviewRun.id == review_run_id)
        )
        res = await session.execute(stmt)
        review_run = res.scalars().first()

        if not review_run:
            raise ValueError(f"ReviewRun '{review_run_id}' not found.")

        pr = review_run.review_job.pull_request if review_run.review_job else None
        if not pr:
            raise ValueError(f"PullRequest relation missing for ReviewRun '{review_run_id}'.")

        report = await self.report_service.get_report(session, review_run_id)
        if not report:
            report = await self.report_service.generate_and_persist_report(session, review_run_id)

        s = report.summary
        if not s.is_mergeable or s.critical_count > 0 or s.risk_grade == RiskGrade.F:
            conclusion = "failure"
        elif s.high_count > 0 or s.risk_grade in [RiskGrade.D, RiskGrade.C]:
            conclusion = "neutral"
        else:
            conclusion = "success"

        comment_markdown = self.format_pr_review_comment(report)
        marker = self.generate_comment_marker(pr.number)
        annotations = self.build_check_run_annotations(report.findings)

        title = f"CodeGuardian: GRADE {s.risk_grade.value} ({s.risk_score:.1f}/100) — {s.recommended_action}"

        return GitHubReportPreview(
            review_run_id=review_run_id,
            pr_number=pr.number,
            comment_markdown=comment_markdown,
            comment_marker=marker,
            check_run_title=title,
            check_run_conclusion=conclusion,
            annotations_count=len(annotations),
            annotations=annotations[:10],
        )

