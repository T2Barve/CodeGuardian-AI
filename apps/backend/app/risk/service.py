import logging
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import ReviewRun
from app.repositories.audit_repository import AuditRepository
from app.repositories.finding_repository import FindingRepository
from app.repositories.review_repository import ReviewRunRepository
from app.risk.engine import RiskEngine
from app.schemas.risk import (
    RepositoryRiskProfile,
    RepositoryTier,
    RiskAssessment,
    RiskCalculationRequest,
)

logger = logging.getLogger("codeguardian.risk.service")


class RiskService:
    """Service handling risk score evaluation, database persistence, and retrieval."""

    @classmethod
    async def assess_and_persist_review_risk(
        cls,
        session: AsyncSession,
        review_run_id: str,
        repo_profile: Optional[RepositoryRiskProfile] = None,
        lines_changed: Optional[int] = None,
        files_changed: Optional[int] = None,
    ) -> RiskAssessment:
        """
        Calculates the deterministic risk score for a ReviewRun and updates the database.
        """
        run_repo = ReviewRunRepository(session)
        finding_repo = FindingRepository(session)
        audit_repo = AuditRepository(session)

        review_run = await run_repo.get(review_run_id)
        if not review_run:
            raise ValueError(f"ReviewRun not found for ID: {review_run_id}")

        findings = await finding_repo.list_by_review_run(review_run_id)

        # Default or extract repo profile
        if repo_profile is None:
            # Check review_run configuration
            config = review_run.configuration or {}
            tier_str = config.get("repo_tier", RepositoryTier.TIER_2.value)
            try:
                repo_profile = RepositoryRiskProfile.from_tier(tier_str)
            except Exception:
                repo_profile = RepositoryRiskProfile.from_tier(RepositoryTier.TIER_2)

        assessment = RiskEngine.calculate_risk(
            findings=findings,
            repo_profile=repo_profile,
            lines_changed=lines_changed,
            files_changed=files_changed,
        )

        # Update ReviewRun in database
        updated_config = dict(review_run.configuration or {})
        updated_config["risk_assessment"] = assessment.model_dump()

        await run_repo.update(
            review_run_id,
            risk_score=assessment.overall_score,
            risk_grade=assessment.grade.value,
            configuration=updated_config,
        )

        # Record audit log
        await audit_repo.record(
            actor="codeguardian-risk-engine",
            action="REVIEW_RISK_ASSESSED",
            resource_type="review_run",
            resource_id=review_run_id,
            metadata_payload={
                "risk_score": assessment.overall_score,
                "risk_grade": assessment.grade.value,
                "risk_level": assessment.level.value,
                "action": assessment.action.value,
                "is_mergeable": assessment.is_mergeable,
            },
        )

        await session.commit()
        logger.info(
            "Persisted risk assessment for ReviewRun %s: score=%.2f, grade=%s, action=%s",
            review_run_id,
            assessment.overall_score,
            assessment.grade.value,
            assessment.action.value,
        )
        return assessment

    @classmethod
    async def get_review_risk(
        cls, session: AsyncSession, review_run_id: str
    ) -> Optional[RiskAssessment]:
        """
        Retrieves the risk assessment for a review run. If already computed,
        returns the cached assessment; otherwise, assesses and persists it.
        """
        run_repo = ReviewRunRepository(session)
        review_run = await run_repo.get(review_run_id)
        if not review_run:
            return None

        config = review_run.configuration or {}
        if "risk_assessment" in config:
            try:
                return RiskAssessment.model_validate(config["risk_assessment"])
            except Exception:
                pass

        # Otherwise compute dynamically
        return await cls.assess_and_persist_review_risk(
            session=session, review_run_id=review_run_id
        )

    @classmethod
    def calculate_stateless(cls, request: RiskCalculationRequest) -> RiskAssessment:
        """
        Stateless risk calculation for API simulation or local CI usage.
        """
        profile = RepositoryRiskProfile.from_tier(request.repo_tier or RepositoryTier.TIER_2)
        return RiskEngine.calculate_risk(
            findings=request.findings,
            repo_profile=profile,
            lines_changed=request.lines_changed,
            files_changed=request.files_changed,
        )
