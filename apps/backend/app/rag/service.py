import os
from pathlib import Path
from typing import List, Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import Policy, PolicyChunk
from app.rag.chunker import PolicyChunker
from app.rag.retriever import PolicyRetriever
from app.rag.vector_store import VectorRecord, VectorStoreInterface, get_vector_store
from app.repositories.policy_repository import PolicyChunkRepository, PolicyRepository
from app.schemas.policy import (
    PolicyIngestRequest,
    PolicyIngestResult,
    PolicyResponse,
    PolicyChunkResponse,
    RAGQueryRequest,
    RAGQueryResponse,
)
from app.utils.logging import get_logger

logger = get_logger("rag.service")


class PolicyService:
    def __init__(
        self,
        vector_store: Optional[VectorStoreInterface] = None,
        chunker: Optional[PolicyChunker] = None,
        retriever: Optional[PolicyRetriever] = None,
    ):
        self.vector_store = vector_store or get_vector_store()
        self.chunker = chunker or PolicyChunker()
        self.retriever = retriever or PolicyRetriever(self.vector_store)

    async def ingest_policy(
        self, session: AsyncSession, request: PolicyIngestRequest
    ) -> PolicyIngestResult:
        """
        Ingest a policy document: chunk, create DB entities, and index vectors.
        """
        policy_repo = PolicyRepository(session)
        chunk_repo = PolicyChunkRepository(session)

        # Check if existing policy with same name exists
        existing = await policy_repo.get_by_name(request.name)
        if existing:
            # Delete old vector records
            await self.vector_store.delete_by_policy_id(existing.id)
            policy = existing
            policy.category = request.category
            policy.source = request.source
            policy.version = request.version
            policy.active = True
        else:
            policy = await policy_repo.create(
                name=request.name,
                category=request.category,
                source=request.source,
                version=request.version,
                active=True,
            )

        # Chunk the raw document content
        chunks = self.chunker.chunk_document(
            raw_text=request.content,
            policy_name=policy.name,
            category=policy.category,
            source=policy.source,
            version=policy.version,
            language_scope=request.language_scope,
        )

        vector_records: List[VectorRecord] = []
        created_chunk_refs: List[str] = []

        # If re-ingesting, remove existing DB chunks
        if existing:
            existing_chunks = await chunk_repo.list_by_policy(policy.id)
            for ec in existing_chunks:
                await chunk_repo.delete(ec.id)

        for chunk_item in chunks:
            chunk_ref = f"{policy.id}_{chunk_item.chunk_index}"
            meta = {
                **chunk_item.metadata,
                "policy_id": policy.id,
                "chunk_index": chunk_item.chunk_index,
                "embedding_reference": chunk_ref,
            }

            await chunk_repo.create(
                policy_id=policy.id,
                chunk_index=chunk_item.chunk_index,
                content=chunk_item.content,
                embedding_reference=chunk_ref,
                metadata_payload=meta,
            )

            # Build vector record
            v_record = VectorRecord(
                id=chunk_ref,
                content=chunk_item.content,
                metadata=meta,
            )
            vector_records.append(v_record)
            created_chunk_refs.append(chunk_ref)

        # Add to vector store
        await self.vector_store.add_documents(vector_records)
        await session.commit()

        logger.info(
            f"Successfully ingested policy '{policy.name}' ({policy.category}) "
            f"with {len(chunks)} chunks into vector store and database."
        )

        return PolicyIngestResult(
            policy_id=policy.id,
            name=policy.name,
            category=policy.category,
            chunks_created=len(chunks),
            vector_refs=created_chunk_refs,
            status="INGESTED",
        )

    async def query_policies(
        self, session: AsyncSession, request: RAGQueryRequest
    ) -> RAGQueryResponse:
        """
        Perform semantic search against indexed policy chunks.
        """
        return await self.retriever.retrieve(request)

    async def list_policies(
        self, session: AsyncSession, category: Optional[str] = None
    ) -> List[PolicyResponse]:
        policy_repo = PolicyRepository(session)
        policies = await policy_repo.list_active(category=category)
        
        results: List[PolicyResponse] = []
        for p in policies:
            results.append(
                PolicyResponse(
                    id=p.id,
                    name=p.name,
                    category=p.category,
                    version=p.version,
                    source=p.source,
                    active=p.active,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )
        return results

    async def get_policy_by_id(
        self, session: AsyncSession, policy_id: str
    ) -> Optional[PolicyResponse]:
        policy_repo = PolicyRepository(session)
        policy = await policy_repo.get_with_chunks(policy_id)
        if not policy:
            return None

        chunks = [
            PolicyChunkResponse(
                id=c.id,
                policy_id=c.policy_id,
                chunk_index=c.chunk_index,
                content=c.content,
                embedding_reference=c.embedding_reference,
                metadata_payload=c.metadata_payload,
                created_at=c.created_at,
            )
            for c in sorted(policy.chunks, key=lambda x: x.chunk_index)
        ]

        return PolicyResponse(
            id=policy.id,
            name=policy.name,
            category=policy.category,
            version=policy.version,
            source=policy.source,
            active=policy.active,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
            chunks=chunks,
        )

    async def auto_ingest_directory_policies(
        self, session: AsyncSession, policies_root: Optional[str] = None
    ) -> int:
        """
        Scan disk directory for .md policy standards and auto-ingest into DB & vector store.
        """
        root_path = Path(policies_root or "policies")
        if not root_path.exists():
            # Check relative to workspace root if running from inside apps/backend
            alt_path = Path(__file__).resolve().parents[4] / (policies_root or "policies")
            if alt_path.exists():
                root_path = alt_path
            else:
                alt_path2 = Path("../..") / (policies_root or "policies")
                if alt_path2.exists():
                    root_path = alt_path2
                else:
                    return 0

        ingested_count = 0
        for md_file in root_path.glob("**/*.md"):
            if md_file.name == "README.md":
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
                # Infer category from directory name
                cat = md_file.parent.name.upper()
                if "SECURITY" in cat:
                    category = "SECURITY"
                elif "CODING" in cat or "QUALITY" in cat:
                    category = "QUALITY"
                elif "TEST" in cat:
                    category = "TESTING"
                elif "DOC" in cat:
                    category = "DOCUMENTATION"
                else:
                    category = "GENERAL"

                title = md_file.stem.replace("_", " ").title()

                request = PolicyIngestRequest(
                    name=f"{title} Baseline",
                    category=category,
                    source=str(md_file.as_posix()),
                    version="1.0.0",
                    content=content,
                )
                await self.ingest_policy(session, request)
                ingested_count += 1
            except Exception as e:
                logger.error(f"Failed to auto-ingest policy file '{md_file}': {e}")

        return ingested_count
