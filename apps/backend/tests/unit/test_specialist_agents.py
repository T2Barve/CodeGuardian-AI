import pytest
from app.agents.security import SecurityAgent
from app.agents.quality import QualityAgent
from app.agents.testing import TestingAgent
from app.agents.documentation import DocumentationAgent
from app.agents.dependency import DependencyAgent
from app.agents.graph import build_review_graph
from app.agents.state import ReviewStateInput
from app.services.llm.mock import MockLLMProvider


@pytest.mark.asyncio
async def test_security_agent_cwe_and_secret_redaction():
    """Validates SecurityAgent CWE mapping, exploitability reasoning, and secret token masking."""
    agent = SecurityAgent(llm_provider=MockLLMProvider())

    raw_scanners = [
        {
            "scanner": "bandit",
            "rule_id": "B608:sql_injection",
            "severity": "HIGH",
            "confidence": 0.95,
            "file_path": "app/db.py",
            "line_start": 42,
            "line_end": 42,
            "message": "Possible SQL injection vector via string formatting",
            "code_snippet": "query = f'SELECT * FROM users WHERE token = {ghp_1234567890abcdef1234567890abcdef}'",
        },
        {
            "scanner": "gitleaks",
            "rule_id": "github-pat",
            "severity": "CRITICAL",
            "confidence": 0.99,
            "file_path": "config/keys.env",
            "line_start": 5,
            "line_end": 5,
            "message": "Found hardcoded token ghp_1234567890abcdef1234567890abcdef",
            "code_snippet": "GH_TOKEN=ghp_1234567890abcdef1234567890abcdef",
        }
    ]

    output = await agent.analyze(
        changed_files=["app/db.py", "config/keys.env"],
        diff_content="+ verify = False\n+ GH_TOKEN=ghp_1234567890abcdef1234567890abcdef\n",
        scanner_results=raw_scanners,
    )

    assert len(output.findings) >= 2
    assert output.threat_level == "CRITICAL"

    # Verify CWE mapping & Secret Redaction
    for finding in output.findings:
        assert finding.cwe_id is not None
        assert "ghp_1234567890abcdef1234567890abcdef" not in finding.title
        assert "ghp_1234567890abcdef1234567890abcdef" not in finding.description
        assert finding.exploitability_analysis != ""
        assert finding.recommendation != ""


@pytest.mark.asyncio
async def test_quality_agent_code_smells_and_maintainability():
    """Validates QualityAgent anti-pattern detection and maintainability grading."""
    agent = QualityAgent(llm_provider=MockLLMProvider())

    diff_content = (
        "+ from utils import *\n"
        "+ try:\n"
        "+     do_work()\n"
        "+ except Exception:\n"
        "+     pass\n"
        "+ print('Debug output in prod')\n"
    )

    output = await agent.analyze(
        changed_files=["app/worker.py"],
        diff_content=diff_content,
    )

    assert len(output.findings) >= 3
    smell_types = [f.code_smell_type for f in output.findings]
    assert "ERROR_HANDLING" in smell_types
    assert "COUPLING" in smell_types
    assert "MAINTAINABILITY" in smell_types
    assert output.maintainability_rating in ("B", "C", "D")


@pytest.mark.asyncio
async def test_testing_agent_gap_analysis_and_test_scaffolding():
    """Validates TestingAgent missing test detection and AI-generated starter test scaffolding."""
    agent = TestingAgent(llm_provider=MockLLMProvider())

    diff_content = (
        "--- a/app/billing/processor.py\n"
        "+++ b/app/billing/processor.py\n"
        "+ def process_payment(amount: float, currency: str):\n"
        "+     if amount <= 0:\n"
        "+         raise ValueError('Invalid amount')\n"
        "+     return {'status': 'processed', 'amount': amount}\n"
    )

    output = await agent.analyze(
        changed_files=["app/billing/processor.py"],
        diff_content=diff_content,
    )

    assert len(output.findings) >= 1
    assert len(output.test_gaps) >= 1
    gap = output.test_gaps[0]
    assert gap.untested_symbol == "process_payment"
    assert gap.suggested_test_skeleton is not None
    assert "AI_GENERATED_STARTER_TEST" in gap.suggested_test_skeleton
    assert "def test_process_payment_success" in gap.suggested_test_skeleton


@pytest.mark.asyncio
async def test_documentation_agent_docstring_and_readme_drift():
    """Validates DocumentationAgent missing docstring and README drift warnings."""
    agent = DocumentationAgent(llm_provider=MockLLMProvider())

    diff_content = (
        "--- a/app/api/endpoints/billing.py\n"
        "+++ b/app/api/endpoints/billing.py\n"
        "+ def calculate_vat(subtotal: float):\n"
        "+     return subtotal * 0.20\n"
    )

    output = await agent.analyze(
        changed_files=[
            "app/api/endpoints/billing.py",
            "app/api/endpoints/payments.py",
            "app/api/endpoints/invoices.py",
            "app/api/endpoints/refunds.py",
            "app/api/endpoints/webhooks.py",
        ],
        diff_content=diff_content,
    )

    assert len(output.findings) >= 1
    titles = [f.title for f in output.findings]
    assert any("Missing Public Docstring" in t for t in titles)
    assert any("README" in t for t in titles)


@pytest.mark.asyncio
async def test_dependency_agent_unpinned_and_wildcard_versions():
    """Validates DependencyAgent unpinned, wildcard, and typosquatted dependencies."""
    agent = DependencyAgent(llm_provider=MockLLMProvider())

    diff_content = (
        "--- a/requirements.txt\n"
        "+++ b/requirements.txt\n"
        "+ requests>=2.28.0\n"
        "+ colorama-plus\n"
        "+ unpinned-library\n"
    )

    output = await agent.analyze(
        changed_files=["requirements.txt"],
        diff_content=diff_content,
    )

    assert len(output.findings) >= 3
    risk_types = [f.risk_type for f in output.findings]
    assert "UNPINNED_VERSION" in risk_types
    assert "WILDCARD_VERSION" in risk_types
    assert "SUSPICIOUS_PACKAGE" in risk_types


@pytest.mark.asyncio
async def test_complete_multi_agent_graph_with_all_specialists():
    """Validates end-to-end LangGraph workflow execution with all 5 specialist agents active."""
    app = build_review_graph(llm_provider=MockLLMProvider())

    diff_content = (
        "--- a/app/auth.py\n"
        "+++ b/app/auth.py\n"
        "+ def authenticate_user(token):\n"
        "+     verify = False\n"
        "+     try:\n"
        "+         do_verify(token)\n"
        "+     except Exception:\n"
        "+         pass\n"
        "--- a/requirements.txt\n"
        "+++ b/requirements.txt\n"
        "+ insecure-pkg>=1.0.0\n"
    )

    raw_scan = [{
        "scanner": "bandit",
        "rule_id": "B608:sql_injection",
        "severity": "HIGH",
        "confidence": 0.95,
        "file_path": "app/auth.py",
        "line_start": 5,
        "line_end": 5,
        "message": "Possible SQL injection in user query",
        "code_snippet": "SELECT * FROM users",
    }]

    input_state = ReviewStateInput(
        repo_owner="enterprise-org",
        repo_name="core-service",
        pr_number=101,
        commit_sha="abcdef1234567890",
        changed_files=["app/auth.py", "requirements.txt"],
        diff_content=diff_content,
        normalized_scan_results=raw_scan,
    )

    final_state = await app.ainvoke(input_state)

    # Verify that supervisor activated specialist agents and outputs are synthesized
    assert "security" in final_state["active_agents"]
    assert len(final_state["security_findings"]) >= 1
    assert len(final_state["quality_findings"]) >= 1
    assert len(final_state["testing_findings"]) >= 1
    assert len(final_state["dependency_findings"]) >= 1
    assert len(final_state["correlated_findings"]) >= 1
    assert final_state["risk_assessment"] is not None
    assert final_state["summary_report"] != ""
    assert "CodeGuardian AI Review Summary" in final_state["summary_report"]
