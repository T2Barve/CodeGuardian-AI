from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.github.reporter import GitHubReporter
from app.reports.service import ReportService
from app.schemas.errors import ProblemDetailException
from app.schemas.github import GitHubPublishResult, GitHubReportPreview
from app.schemas.report import ReportFormat, ReviewReport

router = APIRouter(prefix="/reviews")
report_service = ReportService()
github_reporter = GitHubReporter()


@router.get(
    "/{review_run_id}/report",
    response_model=ReviewReport,
    summary="Retrieve structured JSON review report",
)
async def get_review_report(
    review_run_id: str,
    db: AsyncSession = Depends(get_db),
) -> ReviewReport:
    try:
        report = await report_service.get_report(db, review_run_id)
        if not report:
            raise ProblemDetailException(
                status_code=status.HTTP_404_NOT_FOUND,
                title="Review Report Not Found",
                detail=f"No report found for ReviewRun '{review_run_id}'.",
            )
        return report
    except ProblemDetailException:
        raise
    except Exception as e:
        raise ProblemDetailException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Report Retrieval Error",
            detail=f"Failed to fetch report for review run '{review_run_id}': {str(e)}",
        )


@router.get(
    "/{review_run_id}/report/markdown",
    summary="Retrieve formatted GitHub Markdown review report",
)
async def get_review_report_markdown(
    review_run_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        report = await report_service.get_report(db, review_run_id)
        if not report:
            raise ProblemDetailException(
                status_code=status.HTTP_404_NOT_FOUND,
                title="Review Report Not Found",
                detail=f"No report found for ReviewRun '{review_run_id}'.",
            )
        markdown_text = report.markdown_content or ""
        return Response(content=markdown_text, media_type="text/markdown")
    except ProblemDetailException:
        raise
    except Exception as e:
        raise ProblemDetailException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Markdown Report Generation Failed",
            detail=f"Failed to render markdown for review run '{review_run_id}': {str(e)}",
        )


@router.post(
    "/{review_run_id}/report/generate",
    response_model=ReviewReport,
    status_code=status.HTTP_201_CREATED,
    summary="Regenerate and persist review report",
)
async def generate_review_report(
    review_run_id: str,
    db: AsyncSession = Depends(get_db),
) -> ReviewReport:
    try:
        return await report_service.generate_and_persist_report(db, review_run_id)
    except Exception as e:
        raise ProblemDetailException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Report Generation Failed",
            detail=f"Failed to compile report for review run '{review_run_id}': {str(e)}",
        )


@router.post(
    "/{review_run_id}/github/publish",
    response_model=GitHubPublishResult,
    status_code=status.HTTP_200_OK,
    summary="Publish Check Run and review summary comment to GitHub",
)
async def publish_github_report(
    review_run_id: str,
    db: AsyncSession = Depends(get_db),
) -> GitHubPublishResult:
    try:
        return await github_reporter.publish_review_report(db, review_run_id)
    except ValueError as ve:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Review Run Not Found",
            detail=str(ve),
        )
    except Exception as e:
        raise ProblemDetailException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="GitHub Publishing Failed",
            detail=f"Failed to publish review to GitHub for '{review_run_id}': {str(e)}",
        )


@router.get(
    "/{review_run_id}/github/preview",
    response_model=GitHubReportPreview,
    summary="Preview GitHub PR review comment and Check Run annotations",
)
async def preview_github_report(
    review_run_id: str,
    db: AsyncSession = Depends(get_db),
) -> GitHubReportPreview:
    try:
        return await github_reporter.preview_github_report(db, review_run_id)
    except ValueError as ve:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Review Run Not Found",
            detail=str(ve),
        )
    except Exception as e:
        raise ProblemDetailException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="GitHub Preview Failed",
            detail=f"Failed to generate GitHub preview for '{review_run_id}': {str(e)}",
        )

