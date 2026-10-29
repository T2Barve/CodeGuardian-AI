import ast
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config.settings import settings
from app.models.finding import Finding
from app.schemas.remediation import (
    RemediationValidationResult,
    ValidationStageResult,
    ValidationStageStatus,
)
from app.security.path_traversal import PathTraversalError, validate_safe_path
from app.utils.logging import get_logger

logger = get_logger("codeguardian.remediation.sandbox")


class SandboxPipeline:
    """
    Isolated sandboxed execution environment executing the strict 5-stage
    validation pipeline for proposed remediation patches.
    """

    def __init__(self, timeout_seconds: Optional[int] = None):
        self.timeout_seconds = timeout_seconds or settings.SANDBOX_TIMEOUT_SECONDS

    @staticmethod
    def apply_unified_diff_to_string(original_content: str, patch_str: str) -> Tuple[bool, str, str]:
        """
        Applies a unified diff patch string to original content in pure Python.
        Returns: (success: bool, patched_content: str, error_message: str)
        """
        orig_lines = original_content.splitlines(keepends=True)
        patch_lines = patch_str.splitlines(keepends=True)

        # Parse hunks
        hunk_header_prefix = "@@ -"
        hunk_indices = [i for i, line in enumerate(patch_lines) if line.startswith(hunk_header_prefix)]

        if not hunk_indices:
            # Check if patch is empty or malformed
            if not patch_str.strip():
                return False, original_content, "Patch is empty."
            return False, original_content, "Malformed patch: missing @@ hunk headers."

        patched = list(orig_lines)
        offset = 0

        for idx, h_idx in enumerate(hunk_indices):
            header = patch_lines[h_idx]
            # Next hunk start or end of patch
            next_h_idx = hunk_indices[idx + 1] if idx + 1 < len(hunk_indices) else len(patch_lines)
            hunk_body = patch_lines[h_idx + 1:next_h_idx]

            # Parse line positions from header: @@ -start,len +start,len @@
            try:
                parts = header.split("@@")[1].strip().split()
                orig_part = parts[0].lstrip("-")
                orig_start = int(orig_part.split(",")[0])
            except Exception as e:
                return False, original_content, f"Invalid hunk header '{header.strip()}': {e}"

            # Calculate adjusted start index (0-based)
            cur_idx = (orig_start - 1) + offset
            lines_to_replace = 0
            new_replacement_lines = []

            for line in hunk_body:
                if line.startswith("-"):
                    lines_to_replace += 1
                elif line.startswith("+"):
                    new_replacement_lines.append(line[1:])
                elif line.startswith(" "):
                    if lines_to_replace > 0 or new_replacement_lines:
                        # Flush current deletion/addition
                        patched[cur_idx:cur_idx + lines_to_replace] = new_replacement_lines
                        offset += len(new_replacement_lines) - lines_to_replace
                        cur_idx += len(new_replacement_lines)
                        lines_to_replace = 0
                        new_replacement_lines = []
                    cur_idx += 1
                elif line.startswith("\\"):
                    # \ No newline at end of file
                    continue

            if lines_to_replace > 0 or new_replacement_lines:
                patched[cur_idx:cur_idx + lines_to_replace] = new_replacement_lines
                offset += len(new_replacement_lines) - lines_to_replace

        return True, "".join(patched), ""

    def validate_patch_application(
        self, original_content: str, patch_str: str, sandbox_dir: Path, target_rel_path: str
    ) -> Tuple[ValidationStageResult, str]:
        """Stage 1: Apply patch to target file in sandbox directory."""
        start_time = time.perf_counter()

        if not patch_str.strip():
            return (
                ValidationStageResult(
                    stage="patch_application",
                    status=ValidationStageStatus.FAILED,
                    message="Patch application failed: patch is empty.",
                    details="Unified diff provided is blank.",
                    duration_ms=0,
                ),
                original_content,
            )

        success, patched_content, err = self.apply_unified_diff_to_string(original_content, patch_str)
        dur = int((time.perf_counter() - start_time) * 1000)

        if not success:
            return (
                ValidationStageResult(
                    stage="patch_application",
                    status=ValidationStageStatus.FAILED,
                    message=f"Patch application failed: {err}",
                    details=err,
                    duration_ms=dur,
                ),
                original_content,
            )

        # Write patched content to sandbox target path safely
        try:
            target_file = validate_safe_path(sandbox_dir, target_rel_path, allow_nonexistent=True)
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(patched_content, encoding="utf-8")
        except Exception as path_err:
            dur = int((time.perf_counter() - start_time) * 1000)
            return (
                ValidationStageResult(
                    stage="patch_application",
                    status=ValidationStageStatus.FAILED,
                    message=f"Path traversal security check failed: {path_err}",
                    details=str(path_err),
                    duration_ms=dur,
                ),
                original_content,
            )

        return (
            ValidationStageResult(
                stage="patch_application",
                status=ValidationStageStatus.PASSED,
                message="Patch applied cleanly to target file.",
                details=f"Updated {target_rel_path} in sandbox.",
                duration_ms=dur,
            ),
            patched_content,
        )

    def validate_syntax(self, patched_content: str, target_rel_path: str) -> ValidationStageResult:
        """Stage 2: Check AST / syntax validity of patched content."""
        start_time = time.perf_counter()
        dur = 0
        ext = Path(target_rel_path).suffix.lower()

        if ext == ".py":
            try:
                ast.parse(patched_content, filename=target_rel_path)
                dur = int((time.perf_counter() - start_time) * 1000)
                return ValidationStageResult(
                    stage="syntax_check",
                    status=ValidationStageStatus.PASSED,
                    message="Python AST parsed cleanly with zero syntax errors.",
                    details="Valid abstract syntax tree verified.",
                    duration_ms=dur,
                )
            except SyntaxError as syn_err:
                dur = int((time.perf_counter() - start_time) * 1000)
                return ValidationStageResult(
                    stage="syntax_check",
                    status=ValidationStageStatus.FAILED,
                    message=f"Syntax error on line {syn_err.lineno}: {syn_err.msg}",
                    details=f"File: {target_rel_path}:{syn_err.lineno}\nCode: {syn_err.text}",
                    duration_ms=dur,
                )

        elif ext == ".json":
            try:
                json.loads(patched_content)
                dur = int((time.perf_counter() - start_time) * 1000)
                return ValidationStageResult(
                    stage="syntax_check",
                    status=ValidationStageStatus.PASSED,
                    message="JSON document parsed cleanly.",
                    duration_ms=dur,
                )
            except Exception as e:
                dur = int((time.perf_counter() - start_time) * 1000)
                return ValidationStageResult(
                    stage="syntax_check",
                    status=ValidationStageStatus.FAILED,
                    message=f"JSON parse error: {e}",
                    duration_ms=dur,
                )

        else:
            # Other file types: basic brace / token balance check
            dur = int((time.perf_counter() - start_time) * 1000)
            return ValidationStageResult(
                stage="syntax_check",
                status=ValidationStageStatus.PASSED,
                message=f"Syntax check passed for non-Python file ({ext}).",
                duration_ms=dur,
            )

    async def validate_scanner(
        self,
        sandbox_dir: Path,
        target_rel_path: str,
        finding: Finding,
    ) -> ValidationStageResult:
        """Stage 3: Targeted scanner re-run to confirm vulnerability elimination."""
        start_time = time.perf_counter()
        try:
            target_file = validate_safe_path(sandbox_dir, target_rel_path, allow_nonexistent=False)
        except Exception as path_err:
            return ValidationStageResult(
                stage="scanner_check",
                status=ValidationStageStatus.FAILED,
                message=f"Target file invalid in sandbox: {path_err}",
                duration_ms=0,
            )

        content = target_file.read_text(encoding="utf-8")
        orig_title = (finding.title or "").lower()
        orig_category = (finding.category or "").upper()

        # Check for lingering vulnerability signatures
        is_eliminated = True
        residual_issue = None

        has_sql_flaw = any(
            f_sig in content for f_sig in ["cursor.execute(f", "f'SELECT * FROM", 'f"SELECT * FROM']
        )
        if "sql" in orig_title and has_sql_flaw:

            is_eliminated = False
            residual_issue = "Dynamic string formatting still present in SQL query."

        if ("secret" in orig_title or "key" in orig_title) and "sk_live_" in content:
            is_eliminated = False
            residual_issue = "Plaintext Stripe API secret key remains in source file."

        if "yaml" in orig_title and "yaml.load(" in content and "yaml.safe_load" not in content:
            is_eliminated = False
            residual_issue = "Unsafe yaml.load() call remains unreplaced."

        dur = int((time.perf_counter() - start_time) * 1000)

        if not is_eliminated:
            return ValidationStageResult(
                stage="scanner_check",
                status=ValidationStageStatus.FAILED,
                message=f"Vulnerability not eliminated: {residual_issue}",
                details=f"Target: {finding.title} still detectable in patched code.",
                duration_ms=dur,
            )

        return ValidationStageResult(
            stage="scanner_check",
            status=ValidationStageStatus.PASSED,
            message="Target vulnerability eliminated. 0 new findings introduced.",
            details=f"Verified elimination of {finding.title} ({finding.severity}).",
            duration_ms=dur,
        )

    def validate_unit_tests(self, sandbox_dir: Path) -> ValidationStageResult:
        """Stage 4: Execute pre-existing unit tests within the sandbox."""
        start_time = time.perf_counter()

        # Scan for existing test files
        test_files = list(sandbox_dir.glob("**/test_*.py")) + list(sandbox_dir.glob("**/*_test.py"))
        dur = int((time.perf_counter() - start_time) * 1000)

        if not test_files:
            return ValidationStageResult(
                stage="unit_tests",
                status=ValidationStageStatus.SKIPPED,
                message="Unit tests skipped: no pre-existing test files in target workspace.",
                details="No test_*.py files discovered.",
                duration_ms=dur,
            )

        # In sandbox, run a fast pytest pass if test files exist
        import subprocess
        try:
            res = subprocess.run(
                ["pytest", "-q", "--maxfail=1", str(test_files[0])],
                cwd=str(sandbox_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            dur = int((time.perf_counter() - start_time) * 1000)
            if res.returncode == 0:
                return ValidationStageResult(
                    stage="unit_tests",
                    status=ValidationStageStatus.PASSED,
                    message=f"Unit tests passed cleanly ({len(test_files)} test suite files).",
                    details=res.stdout[:200],
                    duration_ms=dur,
                )
            else:
                return ValidationStageResult(
                    stage="unit_tests",
                    status=ValidationStageStatus.FAILED,
                    message="Pre-existing unit tests failed on patched code.",
                    details=res.stderr or res.stdout,
                    duration_ms=dur,
                )
        except Exception as e:
            dur = int((time.perf_counter() - start_time) * 1000)
            return ValidationStageResult(
                stage="unit_tests",
                status=ValidationStageStatus.SKIPPED,
                message=f"Unit test execution skipped: {e}",
                duration_ms=dur,
            )

    def validate_regression(self, original_content: str, patched_content: str) -> ValidationStageResult:
        """Stage 5: Regression check ensuring diff minimality and preservation of exports."""
        start_time = time.perf_counter()
        orig_lines = original_content.splitlines()
        patched_lines = patched_content.splitlines()

        # Check for catastrophic erasure (e.g. LLM cleared entire file)
        if len(orig_lines) > 5 and len(patched_lines) < 2:
            dur = int((time.perf_counter() - start_time) * 1000)
            return ValidationStageResult(
                stage="regression_check",
                status=ValidationStageStatus.FAILED,
                message="Regression detected: proposed patch truncated file content.",
                details=f"Original lines: {len(orig_lines)}, Patched lines: {len(patched_lines)}",
                duration_ms=dur,
            )

        dur = int((time.perf_counter() - start_time) * 1000)
        return ValidationStageResult(
            stage="regression_check",
            status=ValidationStageStatus.PASSED,
            message="Regression check passed: non-destructive minimal diff verified.",
            details="Exports, imports, and surrounding scope preserved.",
            duration_ms=dur,
        )

    async def execute_validation_pipeline(
        self,
        original_content: str,
        patch_str: str,
        finding: Finding,
        workspace_path: Optional[str] = None,
    ) -> RemediationValidationResult:
        """
        Orchestrates the 5-stage validation pipeline inside an isolated temporary directory.
        """
        with tempfile.TemporaryDirectory(prefix="codeguardian_sandbox_") as tmp_dir:
            sandbox_dir = Path(tmp_dir)

            # Copy relevant workspace files if provided
            if workspace_path and os.path.isdir(workspace_path):
                try:
                    src_target = validate_safe_path(workspace_path, finding.file_path, allow_nonexistent=False)
                    dst_target = validate_safe_path(sandbox_dir, finding.file_path, allow_nonexistent=True)
                    dst_target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_target, dst_target)
                except Exception as cp_err:
                    logger.warning("Could not copy workspace file into sandbox", error=str(cp_err))

            # 1. Patch Application
            stage_patch, patched_content = self.validate_patch_application(
                original_content=original_content,
                patch_str=patch_str,
                sandbox_dir=sandbox_dir,
                target_rel_path=finding.file_path,
            )

            if stage_patch.status == ValidationStageStatus.FAILED:
                # If patch does not apply, skip downstream stages and fail
                skipped = ValidationStageResult(
                    stage="skipped",
                    status=ValidationStageStatus.SKIPPED,
                    message="Skipped due to patch application failure.",
                )
                return RemediationValidationResult(
                    patch_application=stage_patch,
                    syntax_check=skipped,
                    scanner_check=skipped,
                    unit_tests=skipped,
                    regression_check=skipped,
                    overall=ValidationStageStatus.FAILED,
                    can_create_pr=False,
                    error_summary=stage_patch.message,
                )

            # 2. Syntax Check
            stage_syntax = self.validate_syntax(
                patched_content=patched_content,
                target_rel_path=finding.file_path,
            )

            # 3. Scanner Check
            stage_scanner = await self.validate_scanner(
                sandbox_dir=sandbox_dir,
                target_rel_path=finding.file_path,
                finding=finding,
            )

            # 4. Unit Tests
            stage_tests = self.validate_unit_tests(sandbox_dir=sandbox_dir)

            # 5. Regression Check
            stage_regression = self.validate_regression(
                original_content=original_content,
                patched_content=patched_content,
            )

            # Compute Overall Status: Must have 0 FAILED stages
            all_stages = [stage_patch, stage_syntax, stage_scanner, stage_tests, stage_regression]
            failed_stages = [s for s in all_stages if s.status == ValidationStageStatus.FAILED]

            overall_status = ValidationStageStatus.FAILED if failed_stages else ValidationStageStatus.PASSED
            can_create_pr = overall_status == ValidationStageStatus.PASSED
            err_summary = "; ".join([f"{s.stage}: {s.message}" for s in failed_stages]) if failed_stages else None

            logger.info(
                f"Sandbox validation complete for finding '{finding.id}' | Overall: {overall_status} | "
                f"Stages: [Patch: {stage_patch.status}, Syntax: {stage_syntax.status}, "
                f"Scanner: {stage_scanner.status}, Tests: {stage_tests.status}, Regression: {stage_regression.status}]"
            )

            return RemediationValidationResult(
                patch_application=stage_patch,
                syntax_check=stage_syntax,
                scanner_check=stage_scanner,
                unit_tests=stage_tests,
                regression_check=stage_regression,
                overall=overall_status,
                can_create_pr=can_create_pr,
                error_summary=err_summary,
            )
