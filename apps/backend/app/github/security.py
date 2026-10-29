import hashlib
import hmac
import re
import time
from typing import Optional, Set
from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger("codeguardian.github.security")

# Allowed characters regex pattern for repository, branch, author handles
SAFE_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.\/]+$")

# In-memory fallback delivery store for testing and when Redis is unavailable
_memory_delivery_store: dict[str, float] = {}
DELIVERY_TTL_SECONDS = 86400  # 24 hours


def verify_hmac_signature(
    raw_payload: bytes,
    signature_header: Optional[str],
    secret: Optional[str] = None,
) -> bool:
    """
    Validates GitHub HMAC-SHA256 signature in constant time.
    
    Args:
        raw_payload: Raw request body bytes.
        signature_header: The 'X-Hub-Signature-256' header value.
        secret: Pre-shared webhook secret. Defaults to settings.GITHUB_WEBHOOK_SECRET.
        
    Returns:
        True if the signature is valid; False otherwise.
    """
    if not signature_header:
        logger.warning("Webhook HMAC verification failed: Missing X-Hub-Signature-256 header")
        return False

    if not signature_header.startswith("sha256="):
        logger.warning(
            "Webhook HMAC verification failed: Malformed signature header format",
            extra={"header": signature_header[:16]},
        )
        return False

    webhook_secret = secret or settings.GITHUB_WEBHOOK_SECRET
    if not webhook_secret:
        logger.error("Webhook secret is empty; cannot verify HMAC signature")
        return False

    computed_digest = hmac.new(
        key=webhook_secret.encode("utf-8"),
        msg=raw_payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    expected_signature = f"sha256={computed_digest}"

    # Use constant-time comparison to prevent side-channel timing attacks
    is_valid = hmac.compare_digest(expected_signature, signature_header)
    if not is_valid:
        logger.warning("Webhook HMAC verification failed: Signature mismatch")
    return is_valid


async def record_delivery_idempotency(
    delivery_id: str,
    redis_url: Optional[str] = None,
) -> bool:
    """
    Ensures delivery idempotency via Redis atomic SETNX with 24h expiration.
    Falls back cleanly to an in-memory TTL set if Redis is inaccessible.
    
    Args:
        delivery_id: The unique X-GitHub-Delivery GUID.
        redis_url: Optional Redis connection string. Defaults to settings.REDIS_URL.
        
    Returns:
        True if the delivery ID is new and successfully recorded;
        False if the delivery ID is a duplicate (replay attempt).
    """
    if not delivery_id or not delivery_id.strip():
        return False

    clean_delivery_id = delivery_id.strip()
    cache_key = f"idempotency:github:{clean_delivery_id}"
    target_redis_url = redis_url or settings.REDIS_URL

    # 1. Attempt Redis atomic SETNX with TTL
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(target_redis_url, socket_connect_timeout=0.5)
        # SET key value NX EX 86400: returns True if key was set, None if key already existed
        result = await client.set(cache_key, "1", nx=True, ex=DELIVERY_TTL_SECONDS)
        await client.aclose()
        if result is True:
            return True
        elif result is None:
            logger.warning("Duplicate delivery detected via Redis", extra={"delivery_id": clean_delivery_id})
            return False
    except Exception as exc:
        # Redis offline or unavailable; fallback to in-memory store
        logger.debug(
            "Redis unavailable for idempotency; falling back to memory store",
            extra={"error": str(exc)},
        )

    # 2. In-memory store fallback with automated TTL eviction
    now = time.time()
    # Purge expired keys
    expired_keys = [k for k, exp in _memory_delivery_store.items() if exp < now]
    for k in expired_keys:
        _memory_delivery_store.pop(k, None)

    if clean_delivery_id in _memory_delivery_store:
        logger.warning(
            "Duplicate delivery detected via memory store",
            extra={"delivery_id": clean_delivery_id},
        )
        return False

    _memory_delivery_store[clean_delivery_id] = now + DELIVERY_TTL_SECONDS
    return True


def clear_memory_delivery_store() -> None:
    """Clears the in-memory delivery store (primarily for test teardown)."""
    _memory_delivery_store.clear()


def sanitize_identifier(value: str, field_name: str = "identifier") -> str:
    """
    Sanitizes repository name, branch, or author handles against path traversal
    and command injection characters.
    
    Raises:
        ValueError if the identifier contains illegal characters or path traversal.
    """
    if not value or not isinstance(value, str):
        raise ValueError(f"Invalid {field_name}: Value cannot be empty.")

    stripped = value.strip()
    if ".." in stripped or "\\" in stripped:
        raise ValueError(f"Security violation: {field_name} contains path traversal elements.")

    if not SAFE_IDENTIFIER_PATTERN.match(stripped):
        raise ValueError(
            f"Security violation: {field_name} contains invalid characters. Must match {SAFE_IDENTIFIER_PATTERN.pattern}"
        )

    return stripped


def parse_and_validate_github_url(url: str) -> tuple[str, str]:
    """
    Validates user-supplied repository URL and extracts (owner, repo).
    Protects against SSRF, internal network probing, path traversal, and command injection.
    
    Accepts:
        - https://github.com/owner/repo
        - https://github.com/owner/repo.git
        - github.com/owner/repo
        - owner/repo
        
    Returns:
        tuple[str, str]: (owner, repo_name)
        
    Raises:
        ValueError: If the URL is invalid, malicious, or points to an unsupported host.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Repository URL cannot be empty.")

    cleaned = url.strip()

    # Block SSRF and private IP / localhost access
    lower_url = cleaned.lower()
    blocked_hosts = [
        "localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254",
        "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.",
        "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.",
        "172.27.", "172.28.", "172.29.", "172.30.", "172.31.", "192.168.",
        "::1", "file://", "gopher://", "ftp://", "dict://"
    ]
    for blocked in blocked_hosts:
        if blocked in lower_url:
            raise ValueError(f"Security violation: Target URL contains prohibited host or scheme ({blocked}).")

    from urllib.parse import urlparse
    if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
        if "/" in cleaned and not cleaned.startswith("github.com/"):
            # Could be short format "owner/repo"
            parts = cleaned.split("/")
            if len(parts) == 2:
                owner, repo = parts[0].strip(), parts[1].strip()
                if repo.endswith(".git"):
                    repo = repo[:-4]
                sanitize_identifier(owner, "owner")
                sanitize_identifier(repo, "repository")
                return owner, repo
        cleaned = f"https://{cleaned}"

    parsed = urlparse(cleaned)

    # Restrict scheme strictly to https (or http for internal testing)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme '{parsed.scheme}'. Only https:// is allowed.")

    # Restrict hostname strictly to GitHub
    hostname = (parsed.hostname or "").lower()
    allowed_hostnames = {"github.com", "www.github.com", "api.github.com"}
    if hostname not in allowed_hostnames:
        raise ValueError(f"Invalid repository host '{hostname}'. Only github.com is supported.")

    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(path_parts) < 2:
        raise ValueError("Invalid repository URL format. Expected 'https://github.com/owner/repository'.")

    owner = path_parts[0].strip()
    repo = path_parts[1].strip()

    if repo.endswith(".git"):
        repo = repo[:-4]

    # Validate against path traversal and malicious characters
    sanitize_identifier(owner, "owner")
    sanitize_identifier(repo, "repository")

    if not owner or not repo:
        raise ValueError("Owner and repository name must both be non-empty.")

    return owner, repo

