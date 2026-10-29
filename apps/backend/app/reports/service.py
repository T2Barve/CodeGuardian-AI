from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import AgentRun
from app.models.finding import Finding
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.reports.generator import ReportGenerator
from app.repositories.audit_repository import AuditRepository
from app.repositories.review_repository import ReviewRunRepository
from app.risk.engine import RiskEngine
from app.schemas.report import (
    ReportAgentSummary,
    ReportFindingItem,
    ReviewReport,
    ReviewReportSummary,
)
from app.schemas.risk import CategoryRiskBreakdown, RiskAssessment, RiskGrade, RiskLevel
from app.utils.logging import get_logger

logger = get_logger("reports.service")


class ReportService:
    """
    Coordinates end-to-end review report compilation, database persistence,
    and Markdown/JSON delivery.
    """

    async def generate_and_persist_report(
        self, session: AsyncSession, review_run_id: str
    ) -> ReviewReport:
        # 1. Fetch ReviewRun with relations
        stmt = (
            select(ReviewRun)
            .options(
                selectinload(ReviewRun.review_job)
                .selectinload(ReviewJob.pull_request)
                .selectinload(PullRequest.repository)
            )
            .where(ReviewRun.id == review_run_id)
        )
        result = await session.execute(stmt)
        review_run = result.scalars().first()

        if not review_run:
            raise ValueError(f"ReviewRun '{review_run_id}' not found.")

        pr = review_run.review_job.pull_request if review_run.review_job else None
        repo = pr.repository if pr else None

        repo_name = repo.name if repo else "unknown-repo"
        pr_number = pr.number if pr else 0
        pr_title = pr.title if pr else "Pull Request Review"
        author = pr.author if pr else "developer"
        commit_sha = pr.commit_sha if pr else "00000000"
        source_branch = pr.source_branch if pr else "feature"
        target_branch = pr.target_branch if pr else "main"

        # 2. Fetch Findings with Evidence
        finding_stmt = (
            select(Finding)
            .options(selectinload(Finding.evidence))
            .where(Finding.review_run_id == review_run_id)
        )
        finding_res = await session.execute(finding_stmt)
        db_findings = finding_res.scalars().all()

        report_findings: List[ReportFindingItem] = []
        critical_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0
        info_count = 0

        for f in db_findings:
            sev = f.severity.upper()
            if sev == "CRITICAL":
                critical_count += 1
            elif sev == "HIGH":
                high_count += 1
            elif sev == "MEDIUM":
                medium_count += 1
            elif sev == "LOW":
                low_count += 1
            else:
                info_count += 1

            tools = list({e.tool for e in f.evidence if e.tool})
            code_snip = f.evidence[0].code_snippet if f.evidence else None

            report_findings.append(
                ReportFindingItem(
                    finding_id=f.id,
                    fingerprint=f.fingerprint,
                    category=f.category,
                    severity=f.severity,
                    confidence=f.confidence,
                    file_path=f.file_path,
                    line_start=f.line_start,
                    line_end=f.line_end,
                    title=f.title,
                    description=f.description,
                    impact=f.impact,
                    recommendation=f.recommendation,
                    code_snippet=code_snip,
                    policy_reference=f.policy_reference,
                    tools_involved=tools,
                )
            )

        # 3. Fetch or compute Risk Assessment
        config = review_run.configuration or {}
        risk_data = config.get("risk_assessment")

        if risk_data:
            risk_score = float(risk_data.get("overall_score", risk_data.get("score", 0.0)))
            risk_grade = RiskGrade(risk_data.get("grade", "A"))
            risk_level = RiskLevel(risk_data.get("level", "LOW"))
            is_mergeable = bool(risk_data.get("is_mergeable", True))
            raw_action = risk_data.get("action", risk_data.get("recommended_action", "APPROVE"))
            recommended_action = raw_action.value if hasattr(raw_action, "value") else str(raw_action)
            cb_data = risk_data.get("breakdown", risk_data.get("category_breakdown", {}))
            cat_breakdown = CategoryRiskBreakdown(
                security=cb_data.get("security", 0.0),
                quality=cb_data.get("quality", 0.0),
                testing=cb_data.get("testing", 0.0),
                documentation=cb_data.get("documentation", 0.0),
                dependency=cb_data.get("dependency", 0.0),
            )
            driving_factors = risk_data.get("factors", risk_data.get("driving_factors", []))
        else:
            # Fallback calculate via deterministic risk engine
            risk_assessment = RiskEngine.calculate_risk(findings=report_findings)
            risk_score = risk_assessment.overall_score
            risk_grade = risk_assessment.grade
            risk_level = risk_assessment.level
            is_mergeable = risk_assessment.is_mergeable
            raw_action = risk_assessment.action
            recommended_action = raw_action.value if hasattr(raw_action, "value") else str(raw_action)
            cat_breakdown = risk_assessment.breakdown
            driving_factors = risk_assessment.factors

        # 4. Fetch Agent Runs Telemetry
        agent_stmt = select(AgentRun).where(AgentRun.review_run_id == review_run_id)
        agent_res = await session.execute(agent_stmt)
        db_agents = agent_res.scalars().all()

        agent_summaries: List[ReportAgentSummary] = []
        for ag in db_agents:
            tok = getattr(ag, "total_tokens", 0) or 0
            dur = getattr(ag, "duration_ms", 0) or 0
            agent_summaries.append(
                ReportAgentSummary(
                    agent_name=ag.agent_name,
                    status=ag.status,
                    duration_ms=dur,
                    token_usage=tok,
                    error=ag.error,
                )
            )

        duration_ms = getattr(review_run, "duration_ms", None) or 1200

        # 5. Build Summary & Assemble Report
        summary = ReviewReportSummary(
            review_run_id=review_run.id,
            job_id=review_run.review_job_id,
            repo_name=repo_name,
            pr_number=pr_number,
            pr_title=pr_title,
            author=author,
            commit_sha=commit_sha,
            source_branch=source_branch,
            target_branch=target_branch,
            risk_score=risk_score,
            risk_grade=risk_grade,
            risk_level=risk_level,
            is_mergeable=is_mergeable,
            recommended_action=recommended_action,
            duration_ms=duration_ms,
            total_findings=len(report_findings),
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            info_count=info_count,
        )

        report = ReportGenerator.assemble_report(
            summary=summary,
            category_breakdown=cat_breakdown,
            risk_driving_factors=driving_factors,
            findings=report_findings,
            agent_summaries=agent_summaries,
        )

        # 6. Persist report into ReviewRun configuration
        current_config = dict(review_run.configuration or {})
        current_config["report"] = report.model_dump(mode="json")
        review_run.configuration = current_config
        review_run.summary = report.markdown_content
        await session.commit()

        # 7. Audit log
        audit_repo = AuditRepository(session)
        await audit_repo.create(
            actor="SYSTEM_REPORT_ENGINE",
            action="REVIEW_REPORT_GENERATED",
            resource_type="ReviewRun",
            resource_id=review_run.id,
            metadata_payload={
                "risk_score": risk_score,
                "risk_grade": risk_grade.value,
                "is_mergeable": is_mergeable,
                "findings_count": len(report_findings),
            },
        )
        await session.commit()

        logger.info(
            f"Synthesized review report for ReviewRun '{review_run_id}' "
            f"(Score: {risk_score:.1f}, Grade: {risk_grade.value}, Findings: {len(report_findings)})"
        )

        return report

    async def get_report(
        self, session: AsyncSession, review_run_id: str
    ) -> Optional[ReviewReport]:
        run_repo = ReviewRunRepository(session)
        review_run = await run_repo.get(review_run_id)
        if not review_run:
            return None

        config = review_run.configuration or {}
        report_data = config.get("report")
        if report_data:
            return ReviewReport.model_validate(report_data)

        # If not persisted yet, generate on-demand
        return await self.generate_and_persist_report(session, review_run_id)
