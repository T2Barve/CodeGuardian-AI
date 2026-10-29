import re
from typing import Any, Dict, List, Optional
import structlog

from app.schemas.agent import DocumentationAgentOutput, DocumentationFindingItem
from app.services.llm.base import BaseLLMProvider
from app.services.llm.factory import get_llm_provider

logger = structlog.get_logger(__name__)


class DocumentationAgent:
    """
    Documentation Specialist Agent.
    
    Adheres to docs/AGENT_DESIGN.md Section 3.5:
    - Identifies missing public API docstrings, parameter docs, and type comments.
    - Checks for README / architecture documentation drift when major exports change.
    - Non-intrusive: targets public interfaces without causing notification fatigue.
    """

    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm = llm_provider or get_llm_provider()

    async def analyze(
        self,
        changed_files: List[str],
        diff_content: str,
        retrieved_policies: Optional[List[Dict[str, Any]]] = None,
    ) -> DocumentationAgentOutput:
        """
        Executes documentation health analysis across changed files and diff content.
        """
        findings: List[DocumentationFindingItem] = []

        for file_path in changed_files:
            if "test" in file_path.lower() or "migration" in file_path.lower():
                continue

            # Check Python public functions without docstrings
            if file_path.endswith(".py"):
                doc_findings = self._inspect_python_docs(file_path, diff_content)
                findings.extend(doc_findings)

            # Check TS/JS public exports without JSDoc
            elif file_path.endswith((".ts", ".tsx", ".js")):
                doc_findings = self._inspect_js_docs(file_path, diff_content)
                findings.extend(doc_findings)

        # Check README drift if new major endpoints or dependencies added
        has_new_endpoints = any("endpoint" in f or "api" in f for f in changed_files)
        has_readme_changed = any("readme" in f.lower() for f in changed_files)
        if has_new_endpoints and not has_readme_changed and len(changed_files) >= 5:
            findings.append(
                DocumentationFindingItem(
                    file_path="README.md",
                    line_start=1,
                    line_end=1,
                    title="Potential Documentation Drift (README Not Updated)",
                    doc_type="README",
                    description="Multiple API/service endpoints modified without accompanying README or OpenAPI documentation updates.",
                    recommendation="Ensure README or system documentation reflects newly introduced endpoints and configuration flags.",
                )
            )

        health = "POOR" if len(findings) >= 4 else ("FAIR" if findings else "GOOD")
        summary = (
            f"Documentation analysis identified {len(findings)} documentation gap(s). "
            f"Documentation health: {health}."
        ) if findings else "Documentation satisfies completeness baselines."

        return DocumentationAgentOutput(
            findings=findings,
            summary=summary,
            documentation_health=health,
        )

    def _inspect_python_docs(self, file_path: str, diff_content: str) -> List[DocumentationFindingItem]:
        findings = []
        # Find public functions def func_name(...) without docstring in next line
        lines = diff_content.splitlines()
        for i, line in enumerate(lines):
            match = re.match(r"^\+\s*def\s+([a-zA-Z0-9_]+)\s*\(", line)
            if match:
                func_name = match.group(1)
                # Ignore private functions starting with _
                if func_name.startswith("_"):
                    continue
                # Check if next line contains docstring """
                next_line = lines[i + 1] if i + 1 < len(lines) else ""
                if '"""' not in next_line and "'''" not in next_line:
                    findings.append(
                        DocumentationFindingItem(
                            file_path=file_path,
                            line_start=max(1, i),
                            line_end=max(1, i + 1),
                            title=f"Missing Public Docstring for `{func_name}`",
                            doc_type="DOCSTRING",
                            description=f"Public function `{func_name}` in `{file_path}` is missing structured docstrings.",
                            recommendation=f"Add docstrings detailing function purpose, arguments, return type, and raised exceptions.",
                        )
                    )
        return findings

    def _inspect_js_docs(self, file_path: str, diff_content: str) -> List[DocumentationFindingItem]:
        findings = []
        lines = diff_content.splitlines()
        for i, line in enumerate(lines):
            match = re.match(r"^\+\s*export\s+(?:async\s+)?function\s+([a-zA-Z0-9_]+)", line)
            if match:
                func_name = match.group(1)
                prev_line = lines[i - 1] if i > 0 else ""
                if "*/" not in prev_line and "/**" not in prev_line:
                    findings.append(
                        DocumentationFindingItem(
                            file_path=file_path,
                            line_start=max(1, i),
                            line_end=max(1, i + 1),
                            title=f"Missing JSDoc on Exported Function `{func_name}`",
                            doc_type="DOCSTRING",
                            description=f"Exported TypeScript/JavaScript function `{func_name}` lacks JSDoc annotations.",
                            recommendation=f"Add JSDoc `/** ... */` annotations describing parameters and return types.",
                        )
                    )
        return findings
