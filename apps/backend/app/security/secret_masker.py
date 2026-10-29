import re
from typing import Any, Dict, List, Set, Union
from pydantic import BaseModel

# Regex patterns matching diverse credential formats
SECRET_PATTERNS = [
    # Stripe API Keys
    (r"(sk_live_[0-9a-zA-Z]{24,})", "STRIPE_SECRET_KEY"),
    (r"(rk_live_[0-9a-zA-Z]{24,})", "STRIPE_RESTRICTED_KEY"),
    (r"(sk_test_[0-9a-zA-Z]{24,})", "STRIPE_TEST_KEY"),
    # GitHub Tokens
    (r"(ghp_[0-9a-zA-Z]{36,})", "GITHUB_PAT"),
    (r"(github_pat_[0-9a-zA-Z_]{82,})", "GITHUB_FINE_GRAINED_PAT"),
    (r"(gho_[0-9a-zA-Z]{36,})", "GITHUB_OAUTH_TOKEN"),
    (r"(ghs_[0-9a-zA-Z]{36,})", "GITHUB_APP_TOKEN"),
    # AWS Keys
    (r"(AKIA[0-9A-Z]{16})", "AWS_ACCESS_KEY_ID"),
    (r"(?i)aws_secret_access_key\s*=\s*['\"]?([A-Za-z0-9\/+=]{40})['\"]?", "AWS_SECRET_KEY"),
    # Slack Tokens
    (r"(xox[baprs]-[0-9a-zA-Z]{10,48})", "SLACK_TOKEN"),
    # Private Keys
    (r"(-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----)", "PRIVATE_KEY"),
    # Database Connection Strings with Passwords
    (r"((?:postgres|postgresql|mysql|mongodb|redis):\/\/[^:\s\/]+:)([^@\s\/]+)(@[^\s\/]+)", "DATABASE_PASSWORD"),
    # Bearer Tokens
    (r"(?i)(bearer\s+)([a-zA-Z0-9_\-\.]{25,})", "BEARER_TOKEN"),
    # High-entropy JWT tokens
    (r"(eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_\-.]{10,})", "JWT_TOKEN"),
    # Generic Assignment Secrets
    (
        r"(?i)(password|passwd|secret_key|api_token|auth_token|client_secret|access_token|private_token)\s*[:=]\s*['\"]([^'\"]{8,})['\"]",
        "GENERIC_ASSIGNMENT",
    ),
]

# Sensitive dictionary keys whose values should always be scrubbed
SENSITIVE_FIELD_NAMES: Set[str] = {
    "password",
    "secret",
    "secret_key",
    "api_key",
    "token",
    "access_token",
    "refresh_token",
    "auth_token",
    "authorization",
    "private_key",
    "client_secret",
    "webhook_secret",
    "github_token",
    "stripe_key",
    "aws_secret",
}


def mask_secret(secret_text: str) -> str:
    """
    Non-reversibly masks a secret string.
    Preserves at most the first 4 and last 4 characters for long tokens;
    shorter tokens are completely replaced with '***REDACTED***'.
    """
    if not secret_text:
        return ""
    if len(secret_text) <= 8:
        return "***REDACTED***"
    return f"{secret_text[:4]}***REDACTED***{secret_text[-4:]}"


def mask_secrets_in_text(text: str) -> str:
    """
    Scans freeform text (logs, review comments, error messages, code snippets)
    and replaces all identified high-entropy credentials and secret patterns
    with non-reversible redaction markers.
    """
    if not text:
        return ""

    result = text

    for pattern, name in SECRET_PATTERNS:
        if name == "DATABASE_PASSWORD":
            # Retain scheme and user/host, mask only password
            result = re.sub(pattern, r"\1***REDACTED_PASSWORD***\3", result)
        elif name == "BEARER_TOKEN":
            result = re.sub(pattern, r"\1***REDACTED_TOKEN***", result)
        elif name == "GENERIC_ASSIGNMENT":
            result = re.sub(pattern, r'\1="***REDACTED***"', result)
        elif name == "PRIVATE_KEY":
            result = re.sub(pattern, "[***REDACTED_PRIVATE_KEY***]", result)
        else:
            # Mask the token directly
            def _replace_match(m: re.Match) -> str:
                full_val = m.group(1) if m.groups() else m.group(0)
                return mask_secret(full_val)

            result = re.sub(pattern, _replace_match, result)

    return result


def sanitize_telemetry(data: Any, max_depth: int = 10) -> Any:
    """
    Recursively scrubs dictionary, list, and object telemetry structures
    to guarantee no sensitive tokens or credentials are leaked in API responses or logs.
    """
    if max_depth <= 0:
        return "[TRUNCATED_DEPTH]"

    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_lower = str(k).lower().strip()
            # If the key itself indicates a secret, mask the value entirely
            if any(sens in k_lower for sens in SENSITIVE_FIELD_NAMES):
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = sanitize_telemetry(v, max_depth=max_depth - 1)
        return sanitized

    elif isinstance(data, (list, tuple, set)):
        sanitized_list = [sanitize_telemetry(item, max_depth=max_depth - 1) for item in data]
        return type(data)(sanitized_list) if not isinstance(data, set) else set(sanitized_list)

    elif isinstance(data, BaseModel):
        # Convert Pydantic models to dict, sanitize, and return dict
        return sanitize_telemetry(data.model_dump(), max_depth=max_depth - 1)

    elif isinstance(data, str):
        return mask_secrets_in_text(data)

    return data
