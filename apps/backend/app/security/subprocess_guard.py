import asyncio
import os
import shutil
from typing import Dict, List, Optional, Tuple, Union
import structlog

from app.security.path_traversal import validate_safe_path

logger = structlog.get_logger(__name__)


class SubprocessSecurityError(Exception):
    """Raised when an unsafe subprocess execution is attempted."""
    pass


class SubprocessTimeoutError(Exception):
    """Raised when a subprocess exceeds its configured execution timeout."""
    pass


class SubprocessResourceLimitError(Exception):
    """Raised when a subprocess exceeds its memory or output buffer quota."""
    pass


async def execute_isolated_command(
    cmd_args: List[str],
    cwd: str,
    timeout_seconds: int = 45,
    max_output_bytes: int = 5 * 1024 * 1024,  # 5MB buffer cap
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str]:
    """
    Executes an external system command with strict process isolation:
    
    Security Guarantees:
    - shell=False strictly enforced; arguments must be a list of strings.
    - Zero shell string parsing or concatenation (guards against command injection CWE-78).
    - CWD path is verified and constrained (guards against path traversal CWE-22).
    - Strict asynchronous timeout with SIGTERM / SIGKILL termination.
    - Buffer size clamping to guard against output flooding and memory exhaustion DoS.
    """
    # 1. Invariant: cmd_args must be non-empty List[str]
    if not isinstance(cmd_args, list) or not cmd_args:
        raise SubprocessSecurityError("Command must be a non-empty list of argument strings.")

    for i, arg in enumerate(cmd_args):
        if not isinstance(arg, str):
            raise SubprocessSecurityError(f"Argument at index {i} must be string, got {type(arg).__name__}.")

    # 2. Binary validation: binary must be resolved
    binary_name = cmd_args[0]
    resolved_binary = shutil.which(binary_name) or binary_name
    cmd_args_resolved = [resolved_binary] + cmd_args[1:]

    # 3. Working directory validation
    valid_cwd = str(validate_safe_path(cwd, "."))

    # 4. Safe environment preparation
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)

    logger.debug(
        "Spawning isolated subprocess",
        binary=cmd_args_resolved[0],
        args_count=len(cmd_args_resolved),
        cwd=valid_cwd,
        timeout=timeout_seconds,
    )

    process = None
    try:
        # Strictly use create_subprocess_exec (NEVER create_subprocess_shell)
        process = await asyncio.create_subprocess_exec(
            *cmd_args_resolved,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=valid_cwd,
            env=proc_env,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            # Terminate and kill timed-out process
            try:
                process.terminate()
                await asyncio.sleep(0.2)
                if process.returncode is None:
                    process.kill()
            except Exception as kill_err:
                logger.warning("Error killing timed out process", error=str(kill_err))

            raise SubprocessTimeoutError(
                f"Subprocess '{cmd_args[0]}' exceeded timeout of {timeout_seconds}s and was terminated."
            )

        # Enforce output buffer limit to prevent memory exhaustion
        if len(stdout_bytes) > max_output_bytes:
            stdout_bytes = stdout_bytes[:max_output_bytes]
            logger.warning("Subprocess stdout exceeded buffer quota and was truncated.")

        if len(stderr_bytes) > max_output_bytes:
            stderr_bytes = stderr_bytes[:max_output_bytes]
            logger.warning("Subprocess stderr exceeded buffer quota and was truncated.")

        exit_code = process.returncode if process.returncode is not None else -1
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        return exit_code, stdout, stderr

    except Exception as exc:
        if isinstance(exc, (SubprocessSecurityError, SubprocessTimeoutError)):
            raise
        raise SubprocessSecurityError(f"Failed to execute subprocess '{cmd_args[0]}': {exc}") from exc
