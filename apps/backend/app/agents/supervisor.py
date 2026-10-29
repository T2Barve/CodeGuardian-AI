import os
from typing import Any, Dict, List, Optional, Set, Tuple
import structlog
from pydantic import BaseModel, Field
from app.services.llm.base import BaseLLMProvider

logger = structlog.get_logger(__name__)

# Known dependency manifest files
DEPENDENCY_MANIFEST_PATTERNS = {
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "pipfile",
    "pipfile.lock",
    "go.mod",
    "go.sum",
    "pom.xml",
    "build.gradle",
    "cargo.toml",
    "cargo.lock",
    "gemfile",
    "gemfile.lock",
}

# Known documentation extensions and folders
DOC_EXTENSIONS = {".md", ".rst", ".adoc", ".txt"}
DOC_FOLDER_INDICATORS = {"docs/", "doc/", "documentation/"}

# Source code extensions
CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".go", ".java", ".rs", ".c", ".cpp",
    ".cs", ".php", ".rb", ".html", ".css",
    ".sql", ".sh", ".bash",
}


class SupervisorRoutingDecision(BaseModel):
    """
    Pydantic Schema for Supervisor Agent's Dynamic Dispatch Decision.
    
    Adheres to Section 3.1 of docs/AGENT_DESIGN.md.
    """
    active_agents: List[str] = Field(
        description="List of specialist agents activated for this review, e.g. ['security', 'quality', 'testing']."
    )
    file_partitioning: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Mapping of agent names to their respective relevant file subsets.",
    )
    rationale: str = Field(
        description="Architectural rationale explaining why specific agents were activated or bypassed."
    )


def classify_files_for_review(changed_files: List[str]) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    Deterministic rule-based classification and file partitioning.
    
    Guarantees:
    - High-speed zero-network execution.
    - Deterministic partition mapping for specialist agents.
    - Robust fallback when LLM is unavailable or times out.
    """
    partitioning: Dict[str, List[str]] = {
        "security": [],
        "quality": [],
        "testing": [],
        "documentation": [],
        "dependency": [],
    }

    has_code = False
    has_manifests = False
    has_docs = False
    has_tests = False

    for file_path in changed_files:
        norm_path = file_path.replace("\\", "/").lower()
        base_name = os.path.basename(norm_path)
        _, ext = os.path.splitext(norm_path)

        # 1. Dependency Manifests
        if base_name in DEPENDENCY_MANIFEST_PATTERNS or "requirements" in base_name:
            partitioning["dependency"].append(file_path)
            has_manifests = True

        # 2. Test Files
        is_test = (
            "test_" in base_name
            or "_test." in base_name
            or "/tests/" in norm_path
            or norm_path.startswith("tests/")
            or "/__tests__/" in norm_path
            or "/spec/" in norm_path
        )
        if is_test:
            partitioning["testing"].append(file_path)
            has_tests = True

        # 3. Documentation Files
        is_doc = (
            ext in DOC_EXTENSIONS
            or any(folder in norm_path for folder in DOC_FOLDER_INDICATORS)
            or base_name.startswith("readme")
            or base_name.startswith("changelog")
        )
        if is_doc:
            partitioning["documentation"].append(file_path)
            has_docs = True

        # 4. Source Code Files
        if ext in CODE_EXTENSIONS and not is_test:
            has_code = True
            partitioning["security"].append(file_path)
            partitioning["quality"].append(file_path)
            # Code changes require test gap analysis and docstring check
            partitioning["testing"].append(file_path)
            partitioning["documentation"].append(file_path)

    # Determine activated agents based on detected categories
    active_agents: List[str] = []
    if has_code or len(partitioning["security"]) > 0:
        active_agents.append("security")
        active_agents.append("quality")
    if has_code or has_tests or len(partitioning["testing"]) > 0:
        active_agents.append("testing")
    if has_docs or has_code or len(partitioning["documentation"]) > 0:
        active_agents.append("documentation")
    if has_manifests or len(partitioning["dependency"]) > 0:
        active_agents.append("dependency")

    # If no files matched known rules, activate standard baseline
    if not active_agents:
        active_agents = ["security", "quality", "documentation"]
        for agent in active_agents:
            partitioning[agent] = list(changed_files)

    # Clean up empty partitions
    final_partitioning = {k: v for k, v in partitioning.items() if k in active_agents and len(v) > 0}
    return active_agents, final_partitioning


class SupervisorAgent:
    """
    Lead Architect Orchestrator.
    
    Responsibilities:
    - Evaluates PR context and file change profiles.
    - Dispatches specialist agents conditionally to avoid unnecessary token spend.
    - Employs hybrid LLM reasoning with guaranteed deterministic fallback.
    - Strictly never hallucinates scanner findings.
    """

    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm_provider = llm_provider

    async def evaluate_and_route(
        self,
        repo_name: str,
        pr_number: int,
        changed_files: List[str],
        diff_summary: str = "",
        scanner_results: Optional[List[Dict[str, Any]]] = None,
    ) -> SupervisorRoutingDecision:
        """
        Determines active specialist agents and file partitions for the review run.
        """
        # 1. Compute deterministic baseline classification
        det_agents, det_partitions = classify_files_for_review(changed_files)

        # 2. If scanner results already found issues, guarantee security agent is active
        if scanner_results and len(scanner_results) > 0 and "security" not in det_agents:
            det_agents.append("security")
            det_partitions["security"] = list(changed_files)

        # 3. If LLM provider is configured, enrich routing rationale with architectural reasoning
        if self.llm_provider:
            try:
                system_instruction = (
                    "You are the Lead Software Architect and Supervisor Agent for CodeGuardian AI. "
                    "Analyze the Pull Request file list and diff context. Classify which specialist agents "
                    "must be activated among: ['security', 'quality', 'testing', 'documentation', 'dependency']. "
                    "Partition files to their relevant agents. Provide a concise, professional architectural rationale. "
                    "Never invent scanner evidence."
                )
                prompt = (
                    f"Repository: {repo_name}\n"
                    f"PR #{pr_number}\n"
                    f"Changed Files ({len(changed_files)}):\n" + "\n".join(f"- {f}" for f in changed_files[:50]) + "\n\n"
                    f"Diff Summary Snippet:\n```\n{diff_summary[:1500]}\n```\n\n"
                    f"Baseline Detected Agents: {det_agents}\n"
                    "Provide your structured routing decision."
                )

                decision = await self.llm_provider.generate_structured(
                    prompt=prompt,
                    response_schema=SupervisorRoutingDecision,
                    system_instruction=system_instruction,
                    temperature=0.1,
                )

                # Ensure non-empty active agents and file partitioning
                if decision.active_agents and len(decision.active_agents) > 0:
                    # Sanitize active agents against recognized specialist set
                    valid_specialists = {"security", "quality", "testing", "documentation", "dependency"}
                    sanitized_agents = [a.lower() for a in decision.active_agents if a.lower() in valid_specialists]
                    if sanitized_agents:
                        # Ensure any file partitioning is at least non-empty
                        if not decision.file_partitioning:
                            decision.file_partitioning = det_partitions
                        decision.active_agents = sanitized_agents
                        return decision

            except Exception as exc:
                logger.warning(
                    "Supervisor LLM reasoning failed or timed out; utilizing deterministic routing fallback",
                    error=str(exc),
                )

        # Deterministic fallback return
        rationale_parts = []
        if "security" in det_agents:
            rationale_parts.append(f"Security & Quality agents activated for {len(det_partitions.get('security', []))} code files")
        if "dependency" in det_agents:
            rationale_parts.append(f"Dependency agent activated for {len(det_partitions.get('dependency', []))} manifest files")
        if "testing" in det_agents:
            rationale_parts.append(f"Testing agent activated for test files and logic churn")
        if "documentation" in det_agents:
            rationale_parts.append(f"Documentation agent activated for docs and public API inspection")

        rationale = " | ".join(rationale_parts) if rationale_parts else "Standard multi-agent review triggered."

        return SupervisorRoutingDecision(
            active_agents=det_agents,
            file_partitioning=det_partitions,
            rationale=f"Deterministic Architecture Routing: {rationale}",
        )
