import logging
import sys
from typing import Any, Dict
from app.config.settings import settings


def setup_logging() -> None:
    """Configures structured application logging with sensitive data sanitization."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Suppress verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Returns a named logger configured with application standards."""
    return logging.getLogger(name)


def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Redacts secrets and sensitive keys from log payloads."""
    sensitive_keys = {
        "password", "secret", "token", "authorization", 
        "api_key", "llm_api_key", "webhook_secret", "private_key"
    }
    sanitized = {}
    for k, v in data.items():
        if any(sens in k.lower() for sens in sensitive_keys):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_log_data(v)
        else:
            sanitized[k] = v
    return sanitized
