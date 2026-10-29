from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database.session import get_db
from app.github.service import GitHubWebhookService
from app.schemas.github import WebhookResponse
from app.utils.logging import get_logger

logger = get_logger("codeguardian.api.github")

router = APIRouter(prefix="/github", tags=["GitHub Integration"])


@router.post(
    "/webhook",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=WebhookResponse,
    summary="Ingest GitHub Webhook Event",
    description=(
        "Ingests GitHub webhook events, verifies HMAC-SHA256 signature, ensures "
        "delivery idempotency, and enqueues a background review job for actionable pull request events."
    ),
    responses={
        202: {
            "description": "Webhook accepted and review job successfully enqueued, or non-actionable event acknowledged.",
            "model": WebhookResponse,
        },
        400: {"description": "Malformed JSON payload or invalid headers/unsupported event."},
        401: {"description": "Missing or invalid HMAC SHA-256 signature."},
        409: {"description": "Duplicate delivery ID detected (replay prevention)."},
    },
)
async def github_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
) -> WebhookResponse:
    """
    Receives and processes GitHub Webhook events.
    Verifies HMAC-SHA256 signature and enqueues automated code review.
    """
    raw_body = await request.body()

    service = GitHubWebhookService(session=db)
    result = await service.process_webhook(
        raw_body=raw_body,
        signature_header=x_hub_signature_256,
        event_type=x_github_event,
        delivery_id=x_github_delivery,
    )
    return result
