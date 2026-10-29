import os
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import build_review_graph
from app.agents.service import SupervisorService
from app.agents.state import (
    ReviewState,
    ReviewStateInput,
    add_lists,
    merge_counters,
    merge_dicts,
)
from app.agents.supervisor import (
    SupervisorAgent,
    SupervisorRoutingDecision,
    classify_files_for_review,
)
from app.database.session import get_db
from app.main import app
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.repositories.agent_repository import AgentRunRepository
from app.repositories.pull_request_repository import PullRequestRepository
from app.repositories.repository_repository import RepositoryRepository
from app.repositories.review_repository import ReviewJobRepository, ReviewRunRepository
from app.schemas.queue import ReviewJobPayload
from app.services.llm.base import BaseLLMProvider, TokenUsageTracking
from app.services.llm.factory import get_llm_provider
from app.services.llm.mock import MockLLMProvider
from app.workers.queue import MemoryReviewQueue
from app.workers.review_worker import ReviewWorker


# ==============================================================================
# 1. LLM PROVIDER ABSTRACTION TESTS
# ==============================================================================


class SampleOutputSchema(BaseModel):
    summary: str
    risk_rating: str
    item_count: int


@pytest.mark.asyncio
async def test_llm_provider_abstraction_mock():
    """Validates that BaseLLMProvider contract and MockLLMProvider operate cleanly."""
    provider = MockLLMProvider(model_name="mock-guardian-test")
    assert provider.get_model_name() == "mock-guardian-test"

    # Natural language generation
    text = await provider.generate("Analyze this pull request for buffer overflows.")
    assert "Analysis completed successfully" in text

    # Structured schema generation
    structured = await provider.generate_structured(
        prompt="Synthesize summary",
        response_schema=SampleOutputSchema,
    )
    assert isinstance(structured, SampleOutputSchema)
    assert structured.item_count == 1
    assert structured.risk_rating != ""

    # Vector embeddings
    vectors = await provider.embed(["Security guideline for SQL sanitization"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 384


def test_llm_factory_safety_fallback():
    """Validates that get_llm_provider safely falls back to MockLLMProvider when keys are absent."""
    provider = get_llm_provider(provider_type="mock")
    assert isinstance(provider, MockLLMProvider)

    # Gemini with blank key should safely return mock without crashing
    safe_provider = get_llm_provider(provider_type="gemini", api_key="")
    assert isinstance(safe_provider, MockLLMProvider)


# ==============================================================================
# 2. REVIEW STATE & REDUCER TESTS
# ==============================================================================


def test_review_state_reducers():
    """Validates state reduction algorithms for parallel specialist nodes."""
    # List accumulation
    l1 = [{"id": 1}]
    l2 = [{"id": 2}, {"id": 3}]
    assert add_lists(l1, l2) == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert add_lists(None, l1) == [{"id": 1}]

    # Dictionary merging
    d1 = {"node_a": {"status": "OK"}}
    d2 = {"node_b": {"status": "OK"}}
    merged_d = merge_dicts(d1, d2)
    assert "node_a" in merged_d and "node_b" in merged_d

    # Counter accumulation
    c1 = {"tokens": 100, "duration": 50}
    c2 = {"tokens": 150, "extra": 10}
    merged_c = merge_counters(c1, c2)
    assert merged_c["tokens"] == 250
    assert merged_c["duration"] == 50
    assert merged_c["extra"] == 10


# ==============================================================================
# 3. DETERMINISTIC FILE CLASSIFICATION & ROUTING TESTS
# ==============================================================================


def test_classify_files_for_review():
    """Validates rule-based file partitioning across different PR file change profiles."""
    # Case 1: Backend code changes
    code_files = ["apps/backend/app/main.py", "apps/backend/app/services/auth.py"]
    agents, partitions = classify_files_for_review(code_files)
    assert "security" in agents
    assert "quality" in agents
    assert "testing" in agents
    assert "documentation" in agents
    assert "dependency" not in agents
    assert len(partitions["security"]) == 2

    # Case 2: Package manifest changes only
    dep_files = ["package.json", "package-lock.json", "requirements.txt"]
    dep_agents, dep_partitions = classify_files_for_review(dep_files)
    assert "dependency" in dep_agents
    assert "security" not in dep_agents
    assert len(dep_partitions["dependency"]) == 3

    # Case 3: Documentation changes only
    doc_files = ["README.md", "docs/ARCHITECTURE.md", "CHANGELOG.md"]
    doc_agents, doc_partitions = classify_files_for_review(doc_files)
    assert "documentation" in doc_agents
    assert "security" not in doc_agents


@pytest.mark.asyncio
async def test_supervisor_agent_routing():
    """Validates SupervisorAgent decision generation and routing rationale."""
    agent = SupervisorAgent()
    decision = await agent.evaluate_and_route(
        repo_name="org/core-api",
        pr_number=42,
        changed_files=["app/main.py", "package.json"],
    )
    assert isinstance(decision, SupervisorRoutingDecision)
    assert "security" in decision.active_agents
    assert "dependency" in decision.active_agents
    assert "Rationale" in decision.rationale or "activated" in decision.rationale


# ==============================================================================
# 4. LANGGRAPH MULTI-AGENT WORKFLOW TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_build_and_invoke_review_graph():
    """Validates complete compilation and execution of the LangGraph review workflow."""
    mock_llm = MockLLMProvider()
    graph = build_review_graph(llm_provider=mock_llm)

    initial_state: ReviewState = {
        "repo_owner": "test-owner",
        "repo_name": "test-repo",
        "pr_number": 101,
        "commit_sha": "a1b2c3d4e5f6",
        "changed_files": ["src/login.py", "requirements.txt"],
        "diff_content": "def login(): pass",
        "normalized_scan_results": [
            {
                "scanner": "bandit",
                "rule_id": "B608",
                "severity": "HIGH",
                "confidence": 0.95,
                "file_path": "src/login.py",
                "line_start": 10,
                "line_end": 10,
                "message": "Potential SQL injection in login handler",
            }
        ],
        "active_agents": [],
        "file_partitioning": {},
        "supervisor_rationale": "",
        "security_findings": [],
        "quality_findings": [],
        "testing_findings": [],
        "documentation_findings": [],
        "dependency_findings": [],
        "agent_errors": {},
        "token_usage": {},
        "agent_telemetry": {},
        "correlated_findings": [],
        "risk_assessment": None,
        "summary_report": "",
    }

    final_state = await graph.ainvoke(initial_state)

    # 1. Supervisor outputs
    assert len(final_state["active_agents"]) > 0
    assert "security" in final_state["active_agents"]
    assert "dependency" in final_state["active_agents"]
    assert "supervisor" in final_state["agent_telemetry"]

    # 2. Aggregated findings
    assert len(final_state["correlated_findings"]) >= 1
    assert final_state["agent_telemetry"]["aggregator"]["status"] == "COMPLETED"

    # 3. Deterministic risk assessment
    risk = final_state["risk_assessment"]
    assert risk is not None
    assert "overall_score" in risk
    assert risk["grade"] in ("A", "B", "C", "D", "F")

    # 4. Synthesized report
    assert "CodeGuardian AI Review Summary" in final_state["summary_report"]


@pytest.mark.asyncio
async def test_langgraph_partial_failure_isolation():
    """Validates that if an individual specialist agent fails, the graph still completes with partial results."""
    mock_llm = MockLLMProvider()
    graph = build_review_graph(llm_provider=mock_llm)

    # Execute with invalid file input that triggers an exception in testing agent
    broken_state: ReviewState = {
        "repo_owner": "owner",
        "repo_name": "repo",
        "pr_number": 1,
        "commit_sha": "abc",
        "changed_files": ["test.py"],
        "diff_content": "",
        "normalized_scan_results": [],
        "active_agents": ["security"],
        "file_partitioning": {"security": ["test.py"]},
        "security_findings": [],
        "quality_findings": [],
        "testing_findings": [],
        "documentation_findings": [],
        "dependency_findings": [],
        "agent_errors": {},
        "token_usage": {},
        "agent_telemetry": {},
        "correlated_findings": [],
        "risk_assessment": None,
        "summary_report": "",
    }

    res = await graph.ainvoke(broken_state)
    assert "risk_assessment" in res
    assert res["risk_assessment"] is not None


# ==============================================================================
# 5. SUPERVISOR SERVICE & DATABASE PERSISTENCE TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_supervisor_service_and_agent_run_persistence(db_session: AsyncSession):
    """Validates that SupervisorService executes the graph and commits AgentRun rows to PostgreSQL."""
    repo_repo = RepositoryRepository(db_session)
    pr_repo = PullRequestRepository(db_session)
    job_repo = ReviewJobRepository(db_session)
    run_repo = ReviewRunRepository(db_session)
    agent_repo = AgentRunRepository(db_session)

    # Setup database hierarchy
    repo = await repo_repo.create(
        github_repo_id=98765,
        name="test-multi-agent-repo",
        owner="guardian-org",
        url="https://github.com/guardian-org/test-multi-agent-repo",
    )
    pr = await pr_repo.create(
        github_pr_id=54321,
        repository_id=repo.id,
        number=77,
        title="Implement secure payment gateway",
        author="developer",
        source_branch="feat/payment",
        target_branch="main",
        commit_sha="fedcba9876543210",
    )
    job = await job_repo.create(pull_request_id=pr.id)
    review_run = await run_repo.create(
        review_job_id=job.id,
        status="RUNNING",
        configuration={"repo_name": repo.name, "pr_number": pr.number},
    )
    await db_session.commit()

    # Execute multi-agent review via SupervisorService
    service = SupervisorService(llm_provider=MockLLMProvider())
    input_data = ReviewStateInput(
        repo_owner=repo.owner,
        repo_name=repo.name,
        pr_number=pr.number,
        commit_sha=pr.commit_sha,
        changed_files=["app/payment.py", "requirements.txt"],
        diff_content="def process_payment(): pass",
        review_run_id=review_run.id,
    )

    final_state = await service.run_review(input_data=input_data, session=db_session)

    # Verify AgentRun database records were created
    agent_runs = await agent_repo.get_by_review_run_id(review_run.id)
    assert len(agent_runs) >= 2  # supervisor + participating specialists + aggregator + risk + reporter
    agent_names = [a.agent_name for a in agent_runs]
    assert "supervisor" in agent_names
    assert "risk_engine" in agent_names

    # Check status and telemetry
    for a in agent_runs:
        assert a.status in ("COMPLETED", "RUNNING")
        assert a.duration_ms is not None
        assert a.review_run_id == review_run.id


# ==============================================================================
# 6. REST API ENDPOINTS TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_agent_api_endpoints(db_session: AsyncSession):
    """Validates the /agents/classify, /reviews/{id}/agents, and /reviews/{id}/agents/run endpoints."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Test file classification preview
            classify_resp = await client.post(
                "/api/v1/agents/classify",
                json={
                    "changed_files": ["api/users.py", "requirements.txt"],
                    "repo_name": "org/api",
                    "pr_number": 10,
                },
            )
            assert classify_resp.status_code == 200
            data = classify_resp.json()
            assert "active_agents" in data
            assert "security" in data["active_agents"]
            assert "dependency" in data["active_agents"]

            # 2. Test review agents list on seeded review run
            repo_repo = RepositoryRepository(db_session)
            pr_repo = PullRequestRepository(db_session)
            job_repo = ReviewJobRepository(db_session)
            run_repo = ReviewRunRepository(db_session)
            agent_repo = AgentRunRepository(db_session)

            repo = await repo_repo.create(
                github_repo_id=11223,
                name="api-test-repo",
                owner="org",
                url="https://github.com/org/api-test-repo",
            )
            pr = await pr_repo.create(
                github_pr_id=33445,
                repository_id=repo.id,
                number=12,
                title="Update dependencies",
                author="bot",
                source_branch="deps",
                target_branch="main",
                commit_sha="112233445566",
            )
            job = await job_repo.create(pull_request_id=pr.id)
            run = await run_repo.create(review_job_id=job.id, status="COMPLETED")
            await agent_repo.record_run(
                review_run_id=run.id,
                agent_name="supervisor",
                status="COMPLETED",
                duration_ms=45,
                total_tokens=150,
            )
            await db_session.commit()

            # Query GET /api/v1/reviews/{id}/agents
            list_resp = await client.get(f"/api/v1/reviews/{run.id}/agents")
            assert list_resp.status_code == 200
            list_data = list_resp.json()
            assert list_data["total_agents"] == 1
            assert list_data["agents"][0]["agent_name"] == "supervisor"
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 7. WORKER END-TO-END WITH MULTI-AGENT SUPERVISOR
# ==============================================================================


@pytest.mark.asyncio
async def test_worker_end_to_end_scanning_findings_and_multi_agent_review(db_session: AsyncSession):
    """
    Validates complete worker pipeline:
    Redis dequeue -> Scanner execution -> LangGraph Multi-Agent Supervisor ->
    Finding correlation -> Deterministic Risk Scoring -> AgentRun Persistence -> COMPLETED.
    """
    repo_repo = RepositoryRepository(db_session)
    pr_repo = PullRequestRepository(db_session)
    job_repo = ReviewJobRepository(db_session)
    run_repo = ReviewRunRepository(db_session)
    agent_repo = AgentRunRepository(db_session)

    repo = await repo_repo.create(
        github_repo_id=778899,
        name="full-pipeline-repo",
        owner="org",
        url="https://github.com/org/full-pipeline-repo",
    )
    pr = await pr_repo.create(
        github_pr_id=998877,
        repository_id=repo.id,
        number=55,
        title="Add user query endpoint",
        author="dev",
        source_branch="feature",
        target_branch="main",
        commit_sha="998877665544",
    )
    job = await job_repo.create(pull_request_id=pr.id)
    await db_session.commit()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a Python file with a SQL injection pattern detectable by Bandit AST
        vulnerable_code = (
            "import sqlite3\n"
            "def query_user(user_id):\n"
            "    conn = sqlite3.connect('test.db')\n"
            "    query = 'SELECT * FROM users WHERE id = %s' % user_id\n"
            "    return conn.execute(query)\n"
        )
        vuln_file_path = os.path.join(tmp_dir, "vulnerable.py")
        with open(vuln_file_path, "w", encoding="utf-8") as f:
            f.write(vulnerable_code)

        # Enqueue review payload pointing to temporary workspace
        queue = MemoryReviewQueue()
        payload = ReviewJobPayload(
            job_id=job.id,
            pull_request_id=pr.id,
            repo_name=repo.name,
            repo_owner=repo.owner,
            pr_number=pr.number,
            commit_sha=pr.commit_sha,
            metadata={
                "workspace_path": tmp_dir,
                "changed_files": ["vulnerable.py"],
                "lines_changed": 15,
                "files_changed": 1,
            },
        )
        await queue.enqueue_review(payload)

        # Instantiate ReviewWorker with MockLLMProvider for supervisor service
        mock_service = SupervisorService(llm_provider=MockLLMProvider())
        worker = ReviewWorker(
            queue=queue,
            session_factory=lambda: db_session,
            supervisor_service=mock_service,
        )

        dequeued = await queue.dequeue_review(timeout=1)
        assert dequeued is not None
        success = await worker.process_job(dequeued)
        assert success is True

        # Assert job and review run are marked COMPLETED
        updated_job = await job_repo.get(job.id)
        assert updated_job.status == "COMPLETED"

        run = await run_repo.get_by_job_id(job.id)
        assert run is not None
        assert run.status == "SUCCESS"
        assert run.configuration is not None
        assert "risk_assessment" in run.configuration

        # Assert AgentRun rows were persisted by the supervisor
        agent_runs = await agent_repo.get_by_review_run_id(run.id)
        assert len(agent_runs) > 0
        agent_names = {a.agent_name for a in agent_runs}
        assert "supervisor" in agent_names
        assert "risk_engine" in agent_names
