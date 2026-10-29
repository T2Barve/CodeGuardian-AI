import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database.session import get_db
from app.main import app
from app.models.base import Base
from app.rag.chunker import PolicyChunker
from app.rag.retriever import PolicyRetriever, ANTI_HALLUCINATION_SENTINEL
from app.rag.service import PolicyService
from app.rag.vector_store import (
    MemoryVectorStore,
    VectorRecord,
    get_vector_store,
    reset_vector_store,
    _cosine_similarity,
    _compute_tf,
    _tokenize,
)
from app.schemas.policy import (
    PolicyIngestRequest,
    RAGQueryRequest,
    RetrievedPolicyChunk,
)


@pytest.fixture(autouse=True)
def clean_vector_store():
    reset_vector_store()
    yield
    reset_vector_store()


@pytest.fixture
async def test_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()


# ==============================================================================
# 1. CHUNKER UNIT TESTS
# ==============================================================================

def test_chunker_markdown_sections():
    chunker = PolicyChunker(max_chunk_chars=1000)
    raw_md = """# Corporate Security Policy

## 1. SQL Injection Prevention
All database queries must use prepared statements or ORM binding.

## 2. Command Injection Defense
Never invoke shell=True or dynamic eval.
"""
    chunks = chunker.chunk_document(
        raw_text=raw_md,
        policy_name="Secure Coding Standard",
        category="SECURITY",
        source="policies/security.md",
        version="1.0.0",
    )

    assert len(chunks) == 2
    assert chunks[0].section == "1. SQL Injection Prevention"
    assert "prepared statements" in chunks[0].content
    assert chunks[0].metadata["category"] == "SECURITY"
    assert chunks[0].metadata["policy_name"] == "Secure Coding Standard"

    assert chunks[1].section == "2. Command Injection Defense"
    assert "shell=True" in chunks[1].content


def test_chunker_empty_and_fallback():
    chunker = PolicyChunker()
    assert chunker.chunk_document("", "Test", "CAT", "source.md") == []

    raw_plain = "This is a simple plain text standard without markdown headers."
    chunks = chunker.chunk_document(raw_plain, "Plain Standard", "GENERAL", "source.txt")
    assert len(chunks) == 1
    assert chunks[0].section == "General Standard"
    assert "plain text standard" in chunks[0].content


# ==============================================================================
# 2. VECTOR STORE & SIMILARITY UNIT TESTS
# ==============================================================================

def test_cosine_similarity_math():
    vec_a = _compute_tf(_tokenize("sql injection prepared statement"))
    vec_b = _compute_tf(_tokenize("sql injection query parameterization"))
    vec_c = _compute_tf(_tokenize("chocolate cake baking recipe"))

    sim_ab = _cosine_similarity(vec_a, vec_b)
    sim_ac = _cosine_similarity(vec_a, vec_c)

    assert sim_ab > 0.40
    assert sim_ac == 0.0


@pytest.mark.asyncio
async def test_memory_vector_store_indexing_and_search():
    store = MemoryVectorStore()
    doc1 = VectorRecord(
        id="chunk_1",
        content="All database queries must use prepared statements to prevent SQL injection.",
        metadata={"category": "SECURITY", "policy_name": "DB Security", "section": "SQLi"},
    )
    doc2 = VectorRecord(
        id="chunk_2",
        content="Functions must maintain cyclomatic complexity below 10.",
        metadata={"category": "QUALITY", "policy_name": "Code Quality", "section": "Complexity"},
    )

    await store.add_documents([doc1, doc2])
    assert await store.count() == 2

    # Search for SQL injection
    results = await store.search(query="SQL injection database statements", threshold=0.30)
    assert len(results) >= 1
    top_record, score = results[0]
    assert top_record.id == "chunk_1"
    assert score > 0.40

    # Category filter
    qual_results = await store.search(query="complexity", category="QUALITY", threshold=0.30)
    assert len(qual_results) == 1
    assert qual_results[0][0].id == "chunk_2"

    sec_filter = await store.search(query="complexity", category="SECURITY", threshold=0.30)
    assert len(sec_filter) == 0

    # Delete
    await store.delete_by_policy_id("non_existent")
    assert await store.count() == 2


# ==============================================================================
# 3. ANTI-HALLUCINATION & RETRIEVER TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_retriever_anti_hallucination_sentinel():
    store = MemoryVectorStore()
    doc = VectorRecord(
        id="chunk_sec",
        content="Store passwords using Argon2id or bcrypt hashing.",
        metadata={"category": "SECURITY", "policy_name": "Crypto Policy", "section": "Passwords"},
    )
    await store.add_documents([doc])

    retriever = PolicyRetriever(vector_store=store)

    # Completely unrelated query
    unrelated_query = RAGQueryRequest(
        query="how to bake a strawberry chocolate cake with vanilla icing",
        similarity_threshold=0.60,
    )
    response = await retriever.retrieve(unrelated_query)

    assert response.results_count == 0
    assert response.chunks == []
    assert response.formatted_context == ANTI_HALLUCINATION_SENTINEL


@pytest.mark.asyncio
async def test_retriever_citation_verification():
    retriever = PolicyRetriever()
    chunk = RetrievedPolicyChunk(
        chunk_id="chk_1",
        policy_id="pol_1",
        policy_name="Secure Coding Standard",
        category="SECURITY",
        section="SQL Injection Prevention",
        source_file="policies/security/secure_coding.md",
        content="Use prepared statements.",
        similarity_score=0.92,
    )

    valid_chunks = [chunk]

    # Valid citations
    assert retriever.verify_citation("As per Secure Coding Standard, use prepared statements", valid_chunks) is True
    assert retriever.verify_citation("Violates section SQL Injection Prevention", valid_chunks) is True
    assert retriever.verify_citation("Ref: policies/security/secure_coding.md", valid_chunks) is True

    # Hallucinated or invalid citations
    assert retriever.verify_citation("According to ISO-27001-MadeUpRule", valid_chunks) is False
    assert retriever.verify_citation(None, valid_chunks) is False
    assert retriever.verify_citation("", valid_chunks) is False


# ==============================================================================
# 4. POLICY SERVICE & DB INTEGRATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_policy_service_ingest_and_query(test_db_session: AsyncSession):
    service = PolicyService()

    ingest_req = PolicyIngestRequest(
        name="API Security Baseline",
        category="SECURITY",
        source="policies/api_sec.md",
        version="1.2.0",
        content="""# API Security Baseline

## 1. Authentication
All API endpoints must enforce JWT bearer token validation.

## 2. Rate Limiting
Public endpoints must enforce maximum 100 requests per minute.
""",
    )

    result = await service.ingest_policy(test_db_session, ingest_req)
    assert result.status == "INGESTED"
    assert result.chunks_created == 2
    assert len(result.vector_refs) == 2

    # Query policies
    query_req = RAGQueryRequest(
        query="JWT token validation authentication",
        category="SECURITY",
        similarity_threshold=0.30,
    )
    rag_resp = await service.query_policies(test_db_session, query_req)
    assert rag_resp.results_count >= 1
    assert "JWT bearer token validation" in rag_resp.formatted_context
    assert "[POLICY CITATION]: API Security Baseline" in rag_resp.formatted_context

    # List policies
    policies = await service.list_policies(test_db_session, category="SECURITY")
    assert len(policies) == 1
    assert policies[0].name == "API Security Baseline"

    # Get by ID with chunks
    policy_detail = await service.get_policy_by_id(test_db_session, result.policy_id)
    assert policy_detail is not None
    assert len(policy_detail.chunks) == 2


@pytest.mark.asyncio
async def test_auto_ingest_directory_policies(test_db_session: AsyncSession):
    service = PolicyService()
    count = await service.auto_ingest_directory_policies(test_db_session, policies_root="policies")
    assert count >= 4  # Secure coding, DB security, Python quality, Test coverage, API docs

    policies = await service.list_policies(test_db_session)
    assert len(policies) >= 4


# ==============================================================================
# 5. REST API ENDPOINTS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_policies_rest_api(test_db_session: AsyncSession):
    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Ingest via API
        ingest_payload = {
            "name": "Testing Guidelines",
            "category": "TESTING",
            "source": "policies/testing.md",
            "version": "1.0.0",
            "content": "## 1. Coverage\nNew code requires 80% test coverage.",
        }
        res = await client.post("/api/v1/policies/ingest", json=ingest_payload)
        assert res.status_code == 201
        data = res.json()
        assert data["chunks_created"] == 1
        policy_id = data["policy_id"]

        # 2. List policies
        res_list = await client.get("/api/v1/policies?category=TESTING")
        assert res_list.status_code == 200
        items = res_list.json()
        assert len(items) >= 1
        assert items[0]["name"] == "Testing Guidelines"

        # 3. Get single policy
        res_get = await client.get(f"/api/v1/policies/{policy_id}")
        assert res_get.status_code == 200
        assert len(res_get.json()["chunks"]) == 1

        # 4. RAG Query API
        query_payload = {
            "query": "test coverage requirements",
            "category": "TESTING",
            "similarity_threshold": 0.20,
        }
        res_rag = await client.post("/api/v1/rag/query", json=query_payload)
        assert res_rag.status_code == 200
        rag_data = res_rag.json()
        assert rag_data["results_count"] >= 1
        assert "80% test coverage" in rag_data["formatted_context"]

    app.dependency_overrides.clear()
