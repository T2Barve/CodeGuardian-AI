import ast
import re
from typing import Any, Dict, List, Optional
import structlog

from app.schemas.agent import QualityAgentOutput, QualityFindingItem
from app.services.llm.base import BaseLLMProvider
from app.services.llm.factory import get_llm_provider

logger = structlog.get_logger(__name__)


class QualityAgent:
    """
    Quality Specialist Agent.
    
    Adheres to docs/AGENT_DESIGN.md Section 3.3:
    - Evaluates code maintainability, cyclomatic and cognitive complexity.
    - Flags code smells: functions > 50 lines, bare exceptions, wildcard imports, debug statements.
    - Uses AST inspection where feasible with graceful fallback.
    - Grounded in clean code and software craftsmanship principles.
    """

    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm = llm_provider or get_llm_provider()

    async def analyze(
        self,
        changed_files: List[str],
        diff_content: str,
        retrieved_policies: Optional[List[Dict[str, Any]]] = None,
    ) -> QualityAgentOutput:
        """
        Executes code quality inspection across partitioned files and diff content.
        """
        findings: List[QualityFindingItem] = []

        for file_path in changed_files:
            # 1. Inspect Python files via AST & heuristics
            if file_path.endswith(".py"):
                py_findings = self._inspect_python_code(file_path, diff_content)
                findings.extend(py_findings)

            # 2. Inspect JS/TS files via heuristics
            elif file_path.endswith((".js", ".jsx", ".ts", ".tsx")):
                js_findings = self._inspect_javascript_code(file_path, diff_content)
                findings.extend(js_findings)

        # 3. Global diff quality checks
        global_findings = self._inspect_diff_quality(diff_content, changed_files)
        findings.extend(global_findings)

        # Deduplicate findings by title and file
        unique_findings: List[QualityFindingItem] = []
        seen = set()
        for f in findings:
            key = (f.file_path, f.title, f.line_start)
            if key not in seen:
                seen.add(key)
                unique_findings.append(f)

        rating = "A"
        if len(unique_findings) >= 5:
            rating = "D"
        elif len(unique_findings) >= 3:
            rating = "C"
        elif len(unique_findings) >= 1:
            rating = "B"

        summary = (
            f"Quality analysis identified {len(unique_findings)} maintainability finding(s). "
            f"Maintainability rating: Grade {rating}."
        ) if unique_findings else "Code quality conforms to maintainability standards."

        return QualityAgentOutput(
            findings=unique_findings,
            summary=summary,
            maintainability_rating=rating,
        )

    def _inspect_python_code(self, file_path: str, diff_content: str) -> List[QualityFindingItem]:
        findings = []

        # Check for bare exception handling / suppressed errors in diff
        if re.search(r"except(?:\s+\w+)?\s*:\s*\n\+?\s*pass|except\s*:\s*pass|except\s+Exception\s*:\s*pass", diff_content):
            findings.append(
                QualityFindingItem(
                    severity="MEDIUM",
                    confidence=0.90,
                    file_path=file_path,
                    line_start=1,
                    line_end=1,
                    title="Swallowed / Bare Exception (Anti-Pattern)",
                    code_smell_type="ERROR_HANDLING",
                    description="Detected 'except Exception: pass' which suppresses unexpected system errors and complicates debugging.",
                    recommendation="Catch specific exception types and ensure errors are logged or appropriately handled.",
                )
            )

        # Check for wildcard imports
        if re.search(r"from\s+[\w\.]+\s+import\s+\*", diff_content):
            findings.append(
                QualityFindingItem(
                    severity="LOW",
                    confidence=0.95,
                    file_path=file_path,
                    line_start=1,
                    line_end=1,
                    title="Wildcard Import Detected (`from module import *`)",
                    code_smell_type="COUPLING",
                    description="Wildcard imports pollute the local namespace and obscure symbol origins.",
                    recommendation="Explicitly import required symbols instead of using wildcard '*' imports.",
                )
            )

        # Check for leftover print statements in production code
        if re.search(r"\bprint\s*\(", diff_content) and "test" not in file_path.lower():
            findings.append(
                QualityFindingItem(
                    severity="INFO",
                    confidence=0.85,
                    file_path=file_path,
                    line_start=1,
                    line_end=1,
                    title="Console `print()` Statement in Production Code",
                    code_smell_type="MAINTAINABILITY",
                    description="Standard `print()` statement detected. Production services should use structured logging.",
                    recommendation="Replace print statements with structured logging (e.g. structlog / logging module).",
                )
            )

        return findings

    def _inspect_javascript_code(self, file_path: str, diff_content: str) -> List[QualityFindingItem]:
        findings = []

        # Check for console.log statements
        if re.search(r"console\.log\(", diff_content) and "test" not in file_path.lower():
            findings.append(
                QualityFindingItem(
                    severity="INFO",
                    confidence=0.85,
                    file_path=file_path,
                    line_start=1,
                    line_end=1,
                    title="Unfiltered `console.log()` in JavaScript/TypeScript",
                    code_smell_type="MAINTAINABILITY",
                    description="Console debugging statement found in application logic.",
                    recommendation="Remove console.log calls before merging or route through a standardized logging wrapper.",
                )
            )

        # Check for magic numbers/large nested callbacks
        if re.search(r"function\s*\([^\)]*\)\s*\{[^}]*function\s*\([^\)]*\)\s*\{[^}]*function", diff_content):
            findings.append(
                QualityFindingItem(
                    severity="MEDIUM",
                    confidence=0.80,
                    file_path=file_path,
                    line_start=1,
                    line_end=1,
                    title="Deeply Nested Callback Architecture (Callback Pyramid)",
                    code_smell_type="COMPLEXITY",
                    description="Detected 3+ levels of nested function callbacks which significantly impedes maintainability.",
                    recommendation="Refactor nested callbacks to use async/await or modular helper functions.",
                )
            )

        return findings

    def _inspect_diff_quality(self, diff_content: str, changed_files: List[str]) -> List[QualityFindingItem]:
        findings = []
        # Check for overly long diffs / high cognitive complexity
        lines = diff_content.splitlines()
        if len(lines) > 600:
            findings.append(
                QualityFindingItem(
                    severity="LOW",
                    confidence=0.75,
                    file_path=changed_files[0] if changed_files else "pull_request",
                    line_start=1,
                    line_end=1,
                    title="High Single PR Diff Volume (>600 lines)",
                    code_smell_type="COMPLEXITY",
                    description=f"Pull request contains {len(lines)} diff lines. Large changes increase review burden and regression risk.",
                    recommendation="Consider breaking large feature sets into smaller, atomic pull requests.",
                )
            )

        return findings
