import time
from typing import List, Optional
from app.rag.vector_store import VectorStoreInterface, get_vector_store
from app.schemas.policy import RAGQueryRequest, RAGQueryResponse, RetrievedPolicyChunk


ANTI_HALLUCINATION_SENTINEL = "[POLICY_CONTEXT]: No applicable project policy was retrieved."


class PolicyRetriever:
    """
    Retrieval-Augmented Generation retrieval engine enforcing anti-hallucination
    guardrails and citation anchoring for multi-agent code reviews.
    """

    def __init__(self, vector_store: Optional[VectorStoreInterface] = None):
        self.vector_store = vector_store or get_vector_store()

    async def retrieve(self, request: RAGQueryRequest) -> RAGQueryResponse:
        start_time = time.perf_counter()

        matches = await self.vector_store.search(
            query=request.query,
            category=request.category,
            top_k=request.top_k,
            threshold=request.similarity_threshold,
        )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if not matches:
            return RAGQueryResponse(
                query=request.query,
                category_filter=request.category,
                results_count=0,
                chunks=[],
                formatted_context=ANTI_HALLUCINATION_SENTINEL,
                retrieval_duration_ms=duration_ms,
            )

        retrieved_chunks: List[RetrievedPolicyChunk] = []
        context_blocks: List[str] = []

        for record, score in matches:
            meta = record.metadata
            chunk = RetrievedPolicyChunk(
                chunk_id=record.id,
                policy_id=meta.get("policy_id", ""),
                policy_name=meta.get("policy_name", "Corporate Engineering Standard"),
                category=meta.get("category", "GENERAL"),
                section=meta.get("section", "General Baseline"),
                source_file=meta.get("source_file", "policies/general.md"),
                content=record.content,
                similarity_score=score,
                metadata=meta,
            )
            retrieved_chunks.append(chunk)

            # Assemble formatted context block
            citation = (
                f"### [POLICY CITATION]: {chunk.policy_name}\n"
                f"- Category: {chunk.category}\n"
                f"- Section: {chunk.section}\n"
                f"- Source: {chunk.source_file}\n"
                f"- Relevance Score: {score:.2f}\n\n"
                f"{chunk.content}\n"
            )
            context_blocks.append(citation)

        formatted_context = "\n---\n".join(context_blocks)

        return RAGQueryResponse(
            query=request.query,
            category_filter=request.category,
            results_count=len(retrieved_chunks),
            chunks=retrieved_chunks,
            formatted_context=formatted_context,
            retrieval_duration_ms=duration_ms,
        )

    def verify_citation(
        self, citation_text: Optional[str], valid_chunks: List[RetrievedPolicyChunk]
    ) -> bool:
        """
        Verify that an agent's claimed policy reference strictly matches
        one of the retrieved chunks for the current review session.
        """
        if not citation_text or not citation_text.strip():
            return False

        citation_lower = citation_text.lower()
        for chunk in valid_chunks:
            if (
                chunk.policy_name.lower() in citation_lower
                or chunk.section.lower() in citation_lower
                or chunk.source_file.lower() in citation_lower
                or chunk.policy_id.lower() in citation_lower
            ):
                return True
        return False
