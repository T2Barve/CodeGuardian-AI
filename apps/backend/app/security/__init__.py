"""
CodeGuardian AI — Enterprise Security Hardening Package
Comprehensive defenses against prompt injection, path traversal, secret leakage,
subprocess escapes, and API security vulnerabilities.
"""

from app.security.prompt_guard import PromptGuard, PromptInspectionResult
from app.security.path_traversal import (
    PathTraversalError,
    sanitize_filename,
    sanitize_relative_path,
    validate_safe_path,
)
from app.security.secret_masker import (
    mask_secret,
    mask_secrets_in_text,
    sanitize_telemetry,
)
from app.security.subprocess_guard import (
    SubprocessResourceLimitError,
    SubprocessSecurityError,
    SubprocessTimeoutError,
    execute_isolated_command,
)
from app.security.middleware import (
    ContentLengthLimitMiddleware,
    SecurityHeadersMiddleware,
)

__all__ = [
    "PromptGuard",
    "PromptInspectionResult",
    "PathTraversalError",
    "sanitize_filename",
    "sanitize_relative_path",
    "validate_safe_path",
    "mask_secret",
    "mask_secrets_in_text",
    "sanitize_telemetry",
    "SubprocessSecurityError",
    "SubprocessTimeoutError",
    "SubprocessResourceLimitError",
    "execute_isolated_command",
    "SecurityHeadersMiddleware",
    "ContentLengthLimitMiddleware",
]
