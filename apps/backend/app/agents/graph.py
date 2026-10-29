import time
from typing import Any, Dict, List, Optional
import structlog
from langgraph.graph import StateGraph, START, END

from app.agents.state import ReviewState
from app.agents.supervisor import SupervisorAgent
from app.agents.security import SecurityAgent
from app.agents.quality import QualityAgent
from app.agents.testing import TestingAgent
from app.agents.documentation import DocumentationAgent
from app.agents.dependency import DependencyAgent
from app.findings.correlation import CorrelatedFinding
from app.findings.engine import FindingEngine
from app.risk.engine import RiskEngine
from app.schemas.risk import RepositoryRiskProfile, RepositoryTier
from app.services.llm.base import BaseLLMProvider

logger = structlog.get_logger(__name__)


def build_review_graph(llm_provider: Optional[BaseLLMProvider] = None) -> Any:
    """
    Constructs and compiles the Master Multi-Agent LangGraph Workflow.
    
    Adheres to Section 1 & Section 3 of docs/AGENT_DESIGN.md:
    1. Supervisor Node analyzes PR changes and partitions files.
    2. Conditional Fan-Out dispatches parallel execution to specialist agents.
    3. State Reducers merge findings and telemetry seamlessly.
    4. Aggregator Node correlates scanner + agent findings.
    5. Deterministic Risk Node calculates reproducible score (0-100) & grade.
    6. Reporter Node synthesizes the executive review report.
    """
    supervisor_agent = SupervisorAgent(llm_provider=llm_provider)
    security_agent = SecurityAgent(llm_provider=llm_provider)
    quality_agent = QualityAgent(llm_provider=llm_provider)
    testing_agent = TestingAgent(llm_provider=llm_provider)
    documentation_agent = DocumentationAgent(llm_provider=llm_provider)
    dependency_agent = DependencyAgent(llm_provider=llm_provider)
    finding_engine = FindingEngine()


    # ==========================================================================
    # NODE 1: SUPERVISOR AGENT
    # ==========================================================================
    async def supervisor_node(state: ReviewState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        repo_name = state.get("repo_name", "unknown")
        pr_number = state.get("pr_number", 0)
        changed_files = state.get("changed_files", [])
        diff_content = state.get("diff_content", "")
        scanner_results = state.get("normalized_scan_results", [])

        try:
            decision = await supervisor_agent.evaluate_and_route(
                repo_name=repo_name,
                pr_number=pr_number,
                changed_files=changed_files,
                diff_summary=diff_content[:2000],
                scanner_results=scanner_results,
            )
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            return {
                "active_agents": decision.active_agents,
                "file_partitioning": decision.file_partitioning,
                "supervisor_rationale": decision.rationale,
                "token_usage": {"supervisor": 85},
                "agent_telemetry": {
                    "supervisor": {
                        "status": "COMPLETED",
                        "duration_ms": duration_ms,
                        "active_agents": decision.active_agents,
                        "rationale": decision.rationale,
                    }
                },
            }
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error("Supervisor node encountered an error", error=str(exc))
            # Fallback to standard code review agents
            fallback_agents = ["security", "quality", "documentation"]
            return {
                "active_agents": fallback_agents,
                "file_partitioning": {a: list(changed_files) for a in fallback_agents},
                "supervisor_rationale": "Supervisor error fallback triggered; default agents activated.",
                "agent_errors": {"supervisor": str(exc)},
                "agent_telemetry": {
                    "supervisor": {
                        "status": "FAILED",
                        "duration_ms": duration_ms,
                        "error": str(exc),
                    }
                },
            }

    # ==========================================================================
    # CONDITIONAL ROUTER
    # ==========================================================================
    def route_to_specialists(state: ReviewState) -> List[str]:
        """Routes execution concurrently to all activated specialist agents."""
        active = state.get("active_agents", [])
        mapping = {
            "security": "security_node",
            "quality": "quality_node",
            "testing": "testing_node",
            "documentation": "documentation_node",
            "dependency": "dependency_node",
        }
        destinations = [mapping[a] for a in active if a in mapping]
        return destinations if destinations else ["aggregator_node"]

    # ==========================================================================
    # NODE 2: SECURITY SPECIALIST AGENT
    # ==========================================================================
    async def security_node(state: ReviewState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        partitioned = state.get("file_partitioning", {}).get("security", [])
        diff_content = state.get("diff_content", "")
        scanners = state.get("normalized_scan_results", [])
        policies = state.get("retrieved_policies", [])

        try:
            output = await security_agent.analyze(
                changed_files=partitioned or state.get("changed_files", []),
                diff_content=diff_content,
                scanner_results=scanners,
                retrieved_policies=policies,
            )
            findings_dicts = [f.model_dump() for f in output.findings]
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            return {
                "security_findings": findings_dicts,
                "token_usage": {"security": 120},
                "agent_telemetry": {
                    "security": {
                        "status": "COMPLETED",
                        "duration_ms": duration_ms,
                        "files_reviewed": len(partitioned),
                        "findings_count": len(findings_dicts),
                        "threat_level": output.threat_level,
                    }
                },
            }
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error("Security agent encountered an error", error=str(exc))
            return {
                "security_findings": [],
                "agent_errors": {"security": str(exc)},
                "agent_telemetry": {
                    "security": {
                        "status": "FAILED",
                        "duration_ms": duration_ms,
                        "error": str(exc),
                    }
                },
            }

    # ==========================================================================
    # NODE 3: QUALITY SPECIALIST AGENT
    # ==========================================================================
    async def quality_node(state: ReviewState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        partitioned = state.get("file_partitioning", {}).get("quality", [])
        diff_content = state.get("diff_content", "")
        policies = state.get("retrieved_policies", [])

        try:
            output = await quality_agent.analyze(
                changed_files=partitioned or state.get("changed_files", []),
                diff_content=diff_content,
                retrieved_policies=policies,
            )
            findings_dicts = [f.model_dump() for f in output.findings]
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            return {
                "quality_findings": findings_dicts,
                "token_usage": {"quality": 95},
                "agent_telemetry": {
                    "quality": {
                        "status": "COMPLETED",
                        "duration_ms": duration_ms,
                        "files_reviewed": len(partitioned),
                        "findings_count": len(findings_dicts),
                        "maintainability_rating": output.maintainability_rating,
                    }
                },
            }
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error("Quality agent encountered an error", error=str(exc))
            return {
                "quality_findings": [],
                "agent_errors": {"quality": str(exc)},
                "agent_telemetry": {
                    "quality": {
                        "status": "FAILED",
                        "duration_ms": duration_ms,
                        "error": str(exc),
                    }
                },
            }

    # ==========================================================================
    # NODE 4: TESTING SPECIALIST AGENT
    # ==========================================================================
    async def testing_node(state: ReviewState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        partitioned = state.get("file_partitioning", {}).get("testing", [])
        changed_files = state.get("changed_files", [])
        diff_content = state.get("diff_content", "")
        policies = state.get("retrieved_policies", [])

        try:
            output = await testing_agent.analyze(
                changed_files=partitioned or changed_files,
                diff_content=diff_content,
                retrieved_policies=policies,
            )
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            return {
                "testing_findings": output.findings,
                "token_usage": {"testing": 70},
                "agent_telemetry": {
                    "testing": {
                        "status": "COMPLETED",
                        "duration_ms": duration_ms,
                        "files_reviewed": len(partitioned),
                        "findings_count": len(output.findings),
                        "test_gaps_count": len(output.test_gaps),
                        "coverage_risk": output.coverage_risk,
                    }
                },
            }
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error("Testing agent encountered an error", error=str(exc))
            return {
                "testing_findings": [],
                "agent_errors": {"testing": str(exc)},
                "agent_telemetry": {
                    "testing": {
                        "status": "FAILED",
                        "duration_ms": duration_ms,
                        "error": str(exc),
                    }
                },
            }

    # ==========================================================================
    # NODE 5: DOCUMENTATION SPECIALIST AGENT
    # ==========================================================================
    async def documentation_node(state: ReviewState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        partitioned = state.get("file_partitioning", {}).get("documentation", [])
        changed_files = state.get("changed_files", [])
        diff_content = state.get("diff_content", "")
        policies = state.get("retrieved_policies", [])

        try:
            output = await documentation_agent.analyze(
                changed_files=partitioned or changed_files,
                diff_content=diff_content,
                retrieved_policies=policies,
            )
            findings_dicts = [f.model_dump() for f in output.findings]
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            return {
                "documentation_findings": findings_dicts,
                "token_usage": {"documentation": 50},
                "agent_telemetry": {
                    "documentation": {
                        "status": "COMPLETED",
                        "duration_ms": duration_ms,
                        "files_reviewed": len(partitioned),
                        "findings_count": len(findings_dicts),
                        "documentation_health": output.documentation_health,
                    }
                },
            }
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error("Documentation agent encountered an error", error=str(exc))
            return {
                "documentation_findings": [],
                "agent_errors": {"documentation": str(exc)},
                "agent_telemetry": {
                    "documentation": {
                        "status": "FAILED",
                        "duration_ms": duration_ms,
                        "error": str(exc),
                    }
                },
            }

    # ==========================================================================
    # NODE 6: DEPENDENCY SPECIALIST AGENT
    # ==========================================================================
    async def dependency_node(state: ReviewState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        partitioned = state.get("file_partitioning", {}).get("dependency", [])
        changed_files = state.get("changed_files", [])
        diff_content = state.get("diff_content", "")
        policies = state.get("retrieved_policies", [])

        try:
            output = await dependency_agent.analyze(
                changed_files=partitioned or changed_files,
                diff_content=diff_content,
                retrieved_policies=policies,
            )
            findings_dicts = [f.model_dump() for f in output.findings]
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            return {
                "dependency_findings": findings_dicts,
                "token_usage": {"dependency": 60},
                "agent_telemetry": {
                    "dependency": {
                        "status": "COMPLETED",
                        "duration_ms": duration_ms,
                        "files_reviewed": len(partitioned),
                        "findings_count": len(findings_dicts),
                        "dependencies_analyzed": output.dependencies_analyzed,
                    }
                },
            }
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error("Dependency agent encountered an error", error=str(exc))
            return {
                "dependency_findings": [],
                "agent_errors": {"dependency": str(exc)},
                "agent_telemetry": {
                    "dependency": {
                        "status": "FAILED",
                        "duration_ms": duration_ms,
                        "error": str(exc),
                    }
                },
            }


    # ==========================================================================
    # NODE 7: AGGREGATOR & CORRELATION NODE
    # ==========================================================================
    async def aggregator_node(state: ReviewState) -> Dict[str, Any]:
        from app.schemas.scanner import NormalizedScanResult, ScannerCategory, ScannerSeverity

        start_time = time.perf_counter()
        all_raw_findings: List[Any] = []

        # Merge findings from all specialist agents
        all_raw_findings.extend(state.get("security_findings", []))
        all_raw_findings.extend(state.get("quality_findings", []))
        all_raw_findings.extend(state.get("testing_findings", []))
        all_raw_findings.extend(state.get("documentation_findings", []))
        all_raw_findings.extend(state.get("dependency_findings", []))

        # Add any raw scanner findings
        scanner_results = state.get("normalized_scan_results", [])
        combined_raw = scanner_results + all_raw_findings

        # Convert dict items into NormalizedScanResult
        normalized_inputs: List[NormalizedScanResult] = []
        for item in combined_raw:
            if isinstance(item, NormalizedScanResult):
                normalized_inputs.append(item)
            elif isinstance(item, dict):
                cat_str = str(item.get("category", "SECURITY")).upper()
                if cat_str not in ScannerCategory.__members__:
                    cat_str = "SECURITY"
                sev_str = str(item.get("severity", "MEDIUM")).upper()
                if sev_str not in ScannerSeverity.__members__:
                    sev_str = "MEDIUM"

                norm = NormalizedScanResult(
                    scanner=item.get("scanner") or item.get("evidence_source", "agent"),
                    rule_id=item.get("rule_id", "rule"),
                    category=ScannerCategory(cat_str),
                    severity=ScannerSeverity(sev_str),
                    confidence=float(item.get("confidence", 0.9)),
                    file_path=item.get("file_path", "unknown"),
                    line_start=item.get("line_start", 1),
                    line_end=item.get("line_end", 1),
                    title=item.get("title", "Review Finding"),
                    message=item.get("message") or item.get("description", "Identified finding"),
                    code_snippet=item.get("code_snippet"),
                    metadata=item.get("metadata", {}),
                )
                normalized_inputs.append(norm)

        # Process and correlate using FindingEngine
        correlated = finding_engine.process_scan_results(normalized_inputs)
        correlated_dicts = [c.to_dict() for c in correlated]

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "correlated_findings": correlated_dicts,
            "agent_telemetry": {
                "aggregator": {
                    "status": "COMPLETED",
                    "duration_ms": duration_ms,
                    "input_findings_count": len(normalized_inputs),
                    "correlated_count": len(correlated_dicts),
                }
            },
        }

    # ==========================================================================
    # NODE 8: DETERMINISTIC RISK SCORING NODE
    # ==========================================================================
    async def risk_node(state: ReviewState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        correlated = state.get("correlated_findings", [])
        files_count = len(state.get("changed_files", []))
        diff_len = len(state.get("diff_content", ""))
        approx_lines = max(1, diff_len // 50)

        # Execute deterministic mathematical calculation
        assessment = RiskEngine.calculate_risk(
            findings=correlated,
            repo_profile=RepositoryRiskProfile.from_tier(RepositoryTier.TIER_2),
            lines_changed=approx_lines,
            files_changed=files_count,
        )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "risk_assessment": assessment.model_dump(),
            "agent_telemetry": {
                "risk_engine": {
                    "status": "COMPLETED",
                    "duration_ms": duration_ms,
                    "score": assessment.overall_score,
                    "grade": assessment.grade.value,
                    "action": assessment.action.value,
                    "is_mergeable": assessment.is_mergeable,
                }
            },
        }

    # ==========================================================================
    # NODE 9: EXECUTIVE REPORT SYNTHESIS NODE
    # ==========================================================================
    async def reporter_node(state: ReviewState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        pr_number = state.get("pr_number", 0)
        repo_name = state.get("repo_name", "unknown")
        commit_sha = state.get("commit_sha", "unknown")[:8]
        active = state.get("active_agents", [])
        rationale = state.get("supervisor_rationale", "No rationale recorded.")
        correlated = state.get("correlated_findings", [])
        risk = state.get("risk_assessment") or {}
        score = risk.get("overall_score", 0.0)
        grade = risk.get("grade", "A")
        action = risk.get("action", "APPROVE")
        is_mergeable = risk.get("is_mergeable", True)

        summary_md = (
            f"## 🛡️ CodeGuardian AI Review Summary — PR #{pr_number}\n\n"
            f"**Repository:** `{repo_name}` | **Commit:** `{commit_sha}`\n"
            f"**Overall Risk Grade:** **{grade}** ({score:.1f}/100) — **Action Recommendation:** `{action}`\n"
            f"**Mergeable Gate Status:** {'✅ APPROVED' if is_mergeable else '❌ BLOCKED'}\n\n"
            f"### Multi-Agent Coordination\n"
            f"- **Active Specialist Agents:** {', '.join(f'`{a}`' for a in active)}\n"
            f"- **Supervisor Routing Rationale:** {rationale}\n\n"
            f"### Finding Overview\n"
            f"- **Total Correlated Issues:** {len(correlated)}\n"
        )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "summary_report": summary_md,
            "agent_telemetry": {
                "reporter": {
                    "status": "COMPLETED",
                    "duration_ms": duration_ms,
                }
            },
        }

    # ==========================================================================
    # GRAPH ASSEMBLY & EDGES
    # ==========================================================================
    workflow = StateGraph(ReviewState)

    # Add Nodes
    workflow.add_node("supervisor_node", supervisor_node)
    workflow.add_node("security_node", security_node)
    workflow.add_node("quality_node", quality_node)
    workflow.add_node("testing_node", testing_node)
    workflow.add_node("documentation_node", documentation_node)
    workflow.add_node("dependency_node", dependency_node)
    workflow.add_node("aggregator_node", aggregator_node)
    workflow.add_node("risk_node", risk_node)
    workflow.add_node("reporter_node", reporter_node)

    # Add Edges
    workflow.add_edge(START, "supervisor_node")
    workflow.add_conditional_edges(
        "supervisor_node",
        route_to_specialists,
        [
            "security_node",
            "quality_node",
            "testing_node",
            "documentation_node",
            "dependency_node",
            "aggregator_node",
        ],
    )

    # Specialist fan-in to Aggregator
    workflow.add_edge("security_node", "aggregator_node")
    workflow.add_edge("quality_node", "aggregator_node")
    workflow.add_edge("testing_node", "aggregator_node")
    workflow.add_edge("documentation_node", "aggregator_node")
    workflow.add_edge("dependency_node", "aggregator_node")

    # Aggregator -> Risk -> Reporter -> END
    workflow.add_edge("aggregator_node", "risk_node")
    workflow.add_edge("risk_node", "reporter_node")
    workflow.add_edge("reporter_node", END)

    return workflow.compile()
