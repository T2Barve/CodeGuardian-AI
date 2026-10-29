import os
import re
from pathlib import Path
from typing import Union
import structlog

logger = structlog.get_logger(__name__)


class PathTraversalError(ValueError):
    """Raised when an untrusted file path attempts to traverse outside permitted boundaries."""
    pass


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes a bare filename, removing path separators, control characters,
    and null bytes to prevent arbitrary file creation or injection.
    """
    if not filename:
        return "unnamed_file"

    # Reject or strip null bytes
    sanitized = filename.replace("\x00", "")

    # Extract basename to neutralize directory paths
    sanitized = os.path.basename(sanitized.replace("\\", "/"))

    # Strip directory separators and dangerous shell characters
    sanitized = re.sub(r'[/\\:*?"<>|]', "_", sanitized)

    # Strip leading dots to prevent hidden file attacks
    sanitized = sanitized.lstrip(".")

    # Enforce standard filesystem filename limit
    sanitized = sanitized[:255].strip()

    return sanitized or "unnamed_file"


def sanitize_relative_path(untrusted_path: str) -> str:
    """
    Cleans a relative path string by stripping leading slashes, backslashes,
    and redundant dot components while checking for obvious traversal signatures.
    """
    if not untrusted_path:
        raise PathTraversalError("File path cannot be empty.")

    if "\x00" in untrusted_path:
        raise PathTraversalError("Null byte injection detected in path.")

    # Normalize backslashes to forward slashes for universal processing
    norm = untrusted_path.replace("\\", "/").strip()

    # Disallow absolute POSIX and Windows drive paths
    if norm.startswith("/") or re.match(r"^[a-zA-Z]:", norm):
        raise PathTraversalError(f"Absolute file paths are forbidden: '{untrusted_path}'")

    # Check for direct directory traversal attempts
    parts = norm.split("/")
    if any(part == ".." for part in parts):
        raise PathTraversalError(f"Directory traversal sequence ('..') detected: '{untrusted_path}'")

    # Clean redundant elements
    clean_parts = [p for p in parts if p and p != "."]
    if not clean_parts:
        if norm in (".", "./"):
            return "."
        raise PathTraversalError("Resolved relative path is empty.")

    return "/".join(clean_parts)


def validate_safe_path(
    base_dir: Union[str, Path],
    untrusted_path: str,
    allow_nonexistent: bool = True,
) -> Path:
    """
    Validates and resolves an untrusted path relative to a base directory,
    strictly enforcing that the resolved destination remains inside the base directory.
    
    Protects against:
    - Path traversal attacks (../, ..\\, etc.)
    - Null-byte injections (CWE-626)
    - Absolute path override attacks
    - Escaping through symlinks (CWE-59)
    
    Returns the resolved Path object if safe.
    Raises PathTraversalError if traversal or breakout is attempted.
    """
    clean_rel = sanitize_relative_path(untrusted_path)

    base_resolved = Path(base_dir).resolve()
    if not base_resolved.exists():
        raise PathTraversalError(f"Base directory does not exist: {base_dir}")
    if not base_resolved.is_dir():
        raise PathTraversalError(f"Base path is not a directory: {base_dir}")

    # Construct candidate path
    target = base_resolved if clean_rel == "." else (base_resolved / clean_rel).resolve()

    # Verification 1: Target must be relative to base_resolved
    try:
        target.relative_to(base_resolved)
    except ValueError:
        logger.warning(
            "Path traversal blocked: target escaped base directory",
            base_dir=str(base_resolved),
            untrusted_path=untrusted_path,
            resolved_target=str(target),
        )
        raise PathTraversalError(
            f"Path traversal detected: '{untrusted_path}' escapes base directory '{base_dir}'."
        )

    # Verification 2: Commonpath check as defense-in-depth
    try:
        common = os.path.commonpath([str(base_resolved), str(target)])
        if os.path.abspath(common) != str(base_resolved):
            raise PathTraversalError(
                f"Path traversal detected via commonpath check: '{untrusted_path}'"
            )
    except Exception as e:
        if not isinstance(e, PathTraversalError):
            raise PathTraversalError(f"Path validation failed: {e}")
        raise

    if not allow_nonexistent and not target.exists():
        raise FileNotFoundError(f"Validated target file does not exist: {target}")

    return target
