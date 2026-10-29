import abc
import asyncio
import os
import shutil
from typing import Any, Dict, List, Optional, Tuple

from app.config.settings import settings
from app.schemas.scanner import NormalizedScanResult
from app.utils.logging import get_logger

logger = get_logger("codeguardian.scanners.base")


class ScannerTimeoutError(Exception):
    """Raised when a static analysis tool exceeds its configured execution timeout."""
    pass


class ScannerExecutionError(Exception):
    """Raised when a scanner subprocess exits with an unexpected non-zero code or error."""
    pass


class BaseScanner(abc.ABC):
    """
    Abstract base class for all SAST scanner adapters.
    Enforces unified subprocess execution, strict timeouts, zero shell usage,
    and typed normalization into NormalizedScanResult.
    """

    def __init__(self, name: str, timeout_seconds: Optional[int] = None):
        self.name = name
        self.timeout_seconds = timeout_seconds or settings.SCANNER_TIMEOUT_SECONDS

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Returns True if the underlying tool binary or internal analyzer is available."""
        pass

    @abc.abstractmethod
    async def scan(
        self, repo_path: str, changed_files: Optional[List[str]] = None
    ) -> List[NormalizedScanResult]:
        """
        Executes static analysis on the target repository or specific changed files.
        Returns a list of standardized NormalizedScanResult instances.
        """
        pass

    def _validate_workspace_path(self, repo_path: str) -> str:
        """
        Ensures repo_path is absolute and points to an existing directory,
        guarding against directory traversal.
        """
        abs_path = os.path.abspath(repo_path)
        if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
            raise ValueError(f"Target repository path does not exist or is not a directory: {repo_path}")
        return abs_path

    def _validate_relative_file_path(self, repo_root: str, file_path: str) -> str:
        """
        Validates that a relative file path does not escape the repository root (path traversal defense).
        Returns the safe absolute path if valid, or raises ValueError if malicious.
        """
        abs_root = self._validate_workspace_path(repo_root)
        clean_rel = os.path.normpath(file_path).lstrip("/\\")
        target_path = os.path.abspath(os.path.join(abs_root, clean_rel))
        common = os.path.commonpath([abs_root, target_path])
        if common != abs_root:
            raise ValueError(
                f"Path traversal detected: '{file_path}' attempts to escape repository root '{repo_root}'."
            )
        return target_path

    async def _run_subprocess(
        self,
        args: List[str],
        cwd: str,
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str, str]:
        """
        Executes an external system tool using asyncio.create_subprocess_exec.
        
        Mandatory Security Invariants:
          - NO shell=True or os.system() (strictly forbidden per Rule 5).
          - Arguments passed strictly as a validated List[str].
          - Bound by asynchronous timeout to prevent denial-of-service hanging.
        """
        exec_timeout = timeout or self.timeout_seconds
        valid_cwd = self._validate_workspace_path(cwd)

        # Merge environment variables if needed
        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)

        logger.info(
            f"Invoking {self.name} scanner subprocess",
            extra={"binary": args[0], "cwd": valid_cwd, "args_count": len(args)},
        )

        try:
            # Safe subprocess invocation with explicit argument list
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=valid_cwd,
                env=proc_env,
            )

            # Wait for execution bounded by timeout
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=exec_timeout
            )
            exit_code = process.returncode if process.returncode is not None else -1

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            return exit_code, stdout, stderr

        except asyncio.TimeoutError:
            logger.error(
                f"Scanner {self.name} timed out after {exec_timeout}s",
                extra={"cwd": valid_cwd, "timeout": exec_timeout},
            )
            try:
                process.kill()
                await process.wait()
            except Exception:
                pass
            raise ScannerTimeoutError(
                f"Scanner '{self.name}' timed out after {exec_timeout} seconds."
            )
        except FileNotFoundError as exc:
            logger.error(f"Binary not found for scanner {self.name}", extra={"error": str(exc)})
            raise ScannerExecutionError(f"Binary for scanner '{self.name}' was not found: {exc}")
        except Exception as exc:
            logger.error(f"Error running subprocess for {self.name}", extra={"error": str(exc)})
            raise ScannerExecutionError(f"Failed to execute scanner '{self.name}': {exc}")

    def _read_code_snippet(
        self, file_path: str, line_start: Optional[int], line_end: Optional[int]
    ) -> Optional[str]:
        """Safely extracts the relevant code snippet from a source file."""
        if not file_path or not os.path.exists(file_path) or not line_start:
            return None

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            start_idx = max(0, line_start - 1)
            end_idx = min(len(lines), (line_end or line_start))
            snippet_lines = lines[start_idx:end_idx]
            return "".join(snippet_lines).strip()
        except Exception:
            return None
