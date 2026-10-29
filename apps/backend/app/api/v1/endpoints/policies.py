from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.rag.service import PolicyService
from app.schemas.errors import ProblemDetailException
from app.schemas.policy import (
    PolicyCreate,
    PolicyIngestRequest,
    PolicyIngestResult,
    PolicyResponse,
)

router = APIRouter(prefix="/policies")
policy_service = PolicyService()


@router.post(
    "/ingest",
    response_model=PolicyIngestResult,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a policy document into RAG vector store and database",
)
async def ingest_policy(
    payload: PolicyIngestRequest,
    db: AsyncSession = Depends(get_db),
) -> PolicyIngestResult:
    try:
        return await policy_service.ingest_policy(db, payload)
    except Exception as e:
        raise ProblemDetailException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Policy Ingestion Failed",
            detail=f"Failed to ingest policy '{payload.name}': {str(e)}",
        )


@router.get(
    "",
    response_model=List[PolicyResponse],
    summary="List all active engineering policies",
)
async def list_policies(
    category: Optional[str] = Query(None, description="Filter by category (SECURITY, QUALITY, etc.)"),
    db: AsyncSession = Depends(get_db),
) -> List[PolicyResponse]:
    return await policy_service.list_policies(db, category=category)


@router.get(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Retrieve policy details and chunk graph",
)
async def get_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
) -> PolicyResponse:
    policy = await policy_service.get_policy_by_id(db, policy_id)
    if not policy:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Policy Not Found",
            detail=f"No policy found with ID '{policy_id}'.",
        )
    return policy
