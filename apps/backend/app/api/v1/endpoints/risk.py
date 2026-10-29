import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.repositories.review_repository import ReviewRunRepository
from app.risk.service import RiskService
from app.schemas.errors import ProblemDetailException
from app.schemas.risk import RiskAssessment, RiskCalculationRequest

logger = logging.getLogger("codeguardian.api.risk")
router = APIRouter()


@router.get(
    "/reviews/{review_run_id}/risk",
    response_model=RiskAssessment,
    summary="Get Review Risk Assessment",
    description="Retrieve the deterministic composite risk score, grade, radar breakdown, and governance factors.",
)
async def get_review_risk_assessment(
    review_run_id: str,
    db: AsyncSession = Depends(get_db),
) -> RiskAssessment:
    run_repo = ReviewRunRepository(db)
    review_run = await run_repo.get(review_run_id)
    if not review_run:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Review Run Not Found",
            detail=f"No review run found with ID: {review_run_id}",
            type_uri="urn:problem:review-run-not-found",
        )

    assessment = await RiskService.get_review_risk(db, review_run_id)
    if not assessment:
        raise ProblemDetailException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Risk Assessment Failed",
            detail="Could not compute or retrieve risk assessment for the specified review run.",
            type_uri="urn:problem:risk-assessment-failed",
        )
    return assessment


@router.post(
    "/risk/calculate",
    response_model=RiskAssessment,
    summary="Stateless Risk Calculation",
    description="Stateless endpoint to compute deterministic risk scores for arbitrary finding sets and repository tiers.",
)
async def calculate_stateless_risk(
    request: RiskCalculationRequest,
) -> RiskAssessment:
    try:
        return RiskService.calculate_stateless(request)
    except Exception as exc:
        logger.error("Failed to calculate stateless risk: %s", exc, exc_info=True)
        raise ProblemDetailException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Risk Calculation Error",
            detail=str(exc),
            type_uri="urn:problem:risk-calculation-error",
        )
