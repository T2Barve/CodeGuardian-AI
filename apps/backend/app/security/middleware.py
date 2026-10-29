from datetime import datetime, timezone
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger(__name__)

DEFAULT_MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies defense-in-depth OWASP recommended security headers to all HTTP responses.
    Protects against MIME sniffing, clickjacking, inline script execution, and protocol downgrade.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)

        # 1. Prevent MIME type sniffing (CWE-430)
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 2. Prevent Clickjacking / Framing (CWE-1021)
        response.headers["X-Frame-Options"] = "DENY"

        # 3. Modern browser XSS filtering
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 4. Strict Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 5. Content Security Policy (CSP)
        if "Content-Security-Policy" not in response.headers:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "frame-ancestors 'none'; "
                "object-src 'none'; "
                "base-uri 'self'"
            )

        # 6. Permissions Policy (Disables invasive browser hardware features)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), "
            "gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # 7. Strict-Transport-Security (HSTS) if over HTTPS or forwarded proto
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        return response


class ContentLengthLimitMiddleware(BaseHTTPMiddleware):
    """
    Guards API endpoints against Denial-of-Service (DoS) and memory exhaustion
    by rejecting oversized request bodies before parsing into memory.
    """

    def __init__(self, app, max_content_length: int = DEFAULT_MAX_CONTENT_LENGTH):
        super().__init__(app)
        self.max_content_length = max_content_length

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                cl_int = int(content_length)
                if cl_int > self.max_content_length:
                    logger.warning(
                        "Payload rejected: exceeds maximum allowed content length",
                        content_length=cl_int,
                        max_limit=self.max_content_length,
                        path=request.url.path,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "type": "https://codeguardian.io/errors/payload-too-large",
                            "title": "Payload Too Large",
                            "status": 413,
                            "detail": f"Request payload size ({cl_int} bytes) exceeds maximum limit ({self.max_content_length} bytes).",
                            "instance": request.url.path,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                        headers={"Content-Type": "application/problem+json"},
                    )
            except ValueError:
                pass

        return await call_next(request)
