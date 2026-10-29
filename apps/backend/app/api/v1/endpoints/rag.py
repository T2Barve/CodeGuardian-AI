from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.rag.service import PolicyService
from app.schemas.errors import ProblemDetailException
from app.schemas.policy import RAGQueryRequest, RAGQueryResponse

router = APIRouter(prefix="/rag")
policy_service = PolicyService()


@router.post(
    "/query",
    response_model=RAGQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantically query policies and retrieve anti-hallucination grounded context",
)
async def query_rag_policies(
    payload: RAGQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> RAGQueryResponse:
    try:
        return await policy_service.query_policies(db, payload)
    except Exception as e:
        raise ProblemDetailException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="RAG Retrieval Failed",
            detail=f"Error executing semantic policy search: {str(e)}",
        )
