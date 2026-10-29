import re
from typing import Any, Dict, List, Optional
import structlog

from app.schemas.agent import TestingAgentOutput, TestingGapItem
from app.services.llm.base import BaseLLMProvider
from app.services.llm.factory import get_llm_provider

logger = structlog.get_logger(__name__)


class TestingAgent:
    """
    Testing Specialist Agent.
    
    Adheres to docs/AGENT_DESIGN.md Section 3.4:
    - Evaluates test coverage gaps and maps modified logic to existing test suites.
    - Flags modified business logic functions without accompanying test changes.
    - Generates starter unit test scaffolding clearly marked as AI_GENERATED_STARTER_TEST.
    """
    __test__ = False

    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm = llm_provider or get_llm_provider()

    async def analyze(
        self,
        changed_files: List[str],
        diff_content: str,
        retrieved_policies: Optional[List[Dict[str, Any]]] = None,
    ) -> TestingAgentOutput:
        """
        Executes test coverage gap analysis across changed files and diff content.
        """
        findings: List[Dict[str, Any]] = []
        test_gaps: List[TestingGapItem] = []

        # Categorize files
        test_files = [f for f in changed_files if self._is_test_file(f)]
        source_files = [f for f in changed_files if not self._is_test_file(f) and self._is_source_code(f)]

        # Check: Source code modified without any test files
        if source_files and not test_files:
            for src in source_files:
                functions = self._extract_modified_functions(src, diff_content)
                for func_name in functions:
                    skeleton = self._generate_starter_test(src, func_name)
                    test_gaps.append(
                        TestingGapItem(
                            file_path=src,
                            untested_symbol=func_name,
                            risk_level="HIGH" if "auth" in src.lower() or "db" in src.lower() else "MEDIUM",
                            missing_test_type="UNIT",
                            rationale=f"Function '{func_name}' was modified without accompanying test assertions.",
                            suggested_test_skeleton=skeleton,
                        )
                    )

            findings.append({
                "category": "TESTING",
                "severity": "LOW",
                "confidence": 0.85,
                "file_path": source_files[0],
                "line_start": 1,
                "line_end": 1,
                "title": "Missing Accompanying Unit/Integration Tests",
                "description": f"Source code modified across {len(source_files)} file(s) without corresponding test file updates in the PR diff.",
                "recommendation": "Add automated unit tests covering modified functions, edge conditions, and error branches.",
                "rule_id": "TEST-GAP-001",
            })

        # Check for skipped or disabled tests
        if re.search(r"@pytest\.mark\.skip|xit\(|it\.skip\(|describe\.skip\(", diff_content):
            findings.append({
                "category": "TESTING",
                "severity": "MEDIUM",
                "confidence": 0.90,
                "file_path": test_files[0] if test_files else changed_files[0],
                "line_start": 1,
                "line_end": 1,
                "title": "Disabled or Skipped Test Suite Detected",
                "description": "Detected skipped test decorators (@pytest.mark.skip or it.skip) in PR diff.",
                "recommendation": "Avoid merging skipped tests to prevent silent coverage regressions; resolve underlying failures.",
                "rule_id": "TEST-SKIPPED-001",
            })

        coverage_risk = "HIGH" if len(test_gaps) >= 3 else ("MEDIUM" if test_gaps else "LOW")
        summary = (
            f"Testing analysis identified {len(test_gaps)} untested logic symbol(s) across {len(source_files)} source file(s). "
            f"Coverage risk: {coverage_risk}."
        ) if test_gaps else "Test coverage alignment verified."

        return TestingAgentOutput(
            findings=findings,
            test_gaps=test_gaps,
            summary=summary,
            coverage_risk=coverage_risk,
        )

    def _is_test_file(self, file_path: str) -> bool:
        lower = file_path.lower()
        return "test" in lower or "spec" in lower or lower.endswith(("_test.go", "_test.py", ".test.ts", ".spec.ts"))

    def _is_source_code(self, file_path: str) -> bool:
        return file_path.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".rs"))

    def _extract_modified_functions(self, file_path: str, diff_content: str) -> List[str]:
        """Extracts modified function or method names from git diff lines."""
        functions = []
        if file_path.endswith(".py"):
            matches = re.findall(r"^\+\s*def\s+([a-zA-Z_0-9]+)\s*\(", diff_content, re.MULTILINE)
            functions.extend(matches)
        elif file_path.endswith((".js", ".ts", ".tsx")):
            matches = re.findall(r"^\+\s*(?:async\s+)?function\s+([a-zA-Z_0-9]+)\s*\(|^\+\s*const\s+([a-zA-Z_0-9]+)\s*=\s*(?:async\s*)?\(", diff_content, re.MULTILINE)
            for m in matches:
                name = m[0] or m[1]
                if name:
                    functions.append(name)

        return list(set(functions)) or ["main_logic"]

    def _generate_starter_test(self, file_path: str, func_name: str) -> str:
        """Generates starter unit test skeleton marked as AI generated."""
        if file_path.endswith(".py"):
            return (
                f"# AI_GENERATED_STARTER_TEST\n"
                f"import pytest\n\n"
                f"def test_{func_name}_success():\n"
                f"    # Arrange\n"
                f"    # Act\n"
                f"    # Assert\n"
                f"    pass\n\n"
                f"def test_{func_name}_edge_case_error():\n"
                f"    # Test invalid input / exception handling\n"
                f"    pass\n"
            )
        return (
            f"// AI_GENERATED_STARTER_TEST\n"
            f"describe('{func_name}', () => {{\n"
            f"    it('should handle expected input correctly', () => {{\n"
            f"        // Arrange, Act, Assert\n"
            f"    }});\n"
            f"}});\n"
        )
