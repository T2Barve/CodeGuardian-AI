import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict
from pydantic import BaseModel, Field


def add_lists(left: Optional[List[Any]], right: Optional[List[Any]]) -> List[Any]:
    """Reducer that combines lists from concurrent specialist agent nodes."""
    res = list(left or [])
    if right:
        res.extend(right)
    return res


def merge_dicts(left: Optional[Dict[str, Any]], right: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Reducer that merges dictionary payloads from concurrent nodes."""
    res = dict(left or {})
    if right:
        res.update(right)
    return res


def merge_counters(left: Optional[Dict[str, int]], right: Optional[Dict[str, int]]) -> Dict[str, int]:
    """Reducer that accumulates token counts and latency counters."""
    res = dict(left or {})
    if right:
        for k, v in right.items():
            res[k] = res.get(k, 0) + v
    return res


class ReviewState(TypedDict, total=False):
    """
    Central LangGraph State Schema for CodeGuardian AI Multi-Agent Review.
    
    Adheres to Section 2 of docs/AGENT_DESIGN.md.
    Reducers enable seamless, conflict-free parallel execution across specialist agents.
    """
    # Context & PR Metadata
    repo_owner: str
    repo_name: str
    pr_number: int
    commit_sha: str
    changed_files: List[str]
    diff_content: str
    workspace_path: Optional[str]
    review_run_id: Optional[str]

    # Deterministic Tool Evidence & Policies
    normalized_scan_results: List[Dict[str, Any]]
    retrieved_policies: List[Dict[str, Any]]
    ast_metadata: Dict[str, Any]

    # Supervisor Orchestration & Partitioning
    active_agents: List[str]
    file_partitioning: Dict[str, List[str]]
    supervisor_rationale: str

    # Parallel Specialist Agent Findings (Annotated with add_lists reducer)
    security_findings: Annotated[List[Dict[str, Any]], add_lists]
    quality_findings: Annotated[List[Dict[str, Any]], add_lists]
    testing_findings: Annotated[List[Dict[str, Any]], add_lists]
    documentation_findings: Annotated[List[Dict[str, Any]], add_lists]
    dependency_findings: Annotated[List[Dict[str, Any]], add_lists]

    # Execution Telemetry & Error Tracking (Annotated with dictionary reducers)
    agent_errors: Annotated[Dict[str, str], merge_dicts]
    token_usage: Annotated[Dict[str, int], merge_counters]
    agent_telemetry: Annotated[Dict[str, Dict[str, Any]], merge_dicts]

    # Aggregated & Synthesized Results
    correlated_findings: List[Dict[str, Any]]
    risk_assessment: Optional[Dict[str, Any]]
    summary_report: str


class ReviewStateInput(BaseModel):
    """Pydantic model for validating incoming inputs to the LangGraph review workflow."""
    model_config = {"arbitrary_types_allowed": True}

    repo_owner: str
    repo_name: str
    pr_number: int
    commit_sha: str
    changed_files: List[str] = Field(default_factory=list)
    diff_content: str = ""
    workspace_path: Optional[str] = None
    review_run_id: Optional[str] = None
    normalized_scan_results: List[Any] = Field(default_factory=list)
    retrieved_policies: List[Dict[str, Any]] = Field(default_factory=list)
    ast_metadata: Dict[str, Any] = Field(default_factory=dict)
