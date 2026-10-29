import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.session import get_db
from app.models.user import User
from app.utils.logging import get_logger

logger = get_logger("codeguardian.security.auth")

# Token revocation registry for immediate logout invalidation
REVOKED_TOKEN_JIDS: Set[str] = set()

# Token lifetime (24 hours in seconds)
ACCESS_TOKEN_EXPIRE_SECONDS = 86400


def hash_password(password: str) -> str:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with a unique cryptographic salt.
    Format: pbkdf2_sha256$iterations$salt_hex$hash_hex
    """
    salt = secrets.token_bytes(16)
    iterations = 100_000
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${derived.hex()}"


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    """Verifies a plain password against the stored PBKDF2-HMAC-SHA256 hash."""
    if not hashed_password or not hashed_password.startswith("pbkdf2_sha256$"):
        return False
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4:
            return False
        _, iterations_str, salt_hex, expected_hash_hex = parts
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(expected_hash_hex)
        derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(derived, expected_hash)
    except Exception as exc:
        logger.warning(f"Password verification exception: {exc}")
        return False


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _base64url_decode(data_str: str) -> bytes:
    padding = "=" * ((4 - len(data_str) % 4) % 4)
    return base64.urlsafe_b64decode((data_str + padding).encode("utf-8"))


def create_access_token(
    user_id: str,
    username: str,
    role: str = "DEVELOPER",
    expires_in: int = ACCESS_TOKEN_EXPIRE_SECONDS,
) -> str:
    """
    Creates a signed JWT (JWS HMAC-SHA256) access token containing subject and claims.
    """
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    jid = secrets.token_hex(16)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + expires_in,
        "jid": jid,
    }

    header_b64 = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

    signature = hmac.new(settings.SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _base64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Validates signature, expiration, and claims of a JWT access token.
    Raises HTTPException 401 if invalid or expired.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed authorization token structure.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
        provided_sig = _base64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, provided_sig):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        payload_bytes = _base64url_decode(payload_b64)
        payload: Dict[str, Any] = json.loads(payload_bytes.decode("utf-8"))

        # Check expiration
        now = int(time.time())
        exp = payload.get("exp", 0)
        if now >= exp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization token has expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check revocation
        jid = payload.get("jid")
        if jid and jid in REVOKED_TOKEN_JIDS:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked upon logout.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"Failed to decode token: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def revoke_token(token: str) -> None:
    """Adds token jid to revocation blacklist."""
    try:
        parts = token.split(".")
        if len(parts) == 3:
            payload_bytes = _base64url_decode(parts[1])
            payload = json.loads(payload_bytes.decode("utf-8"))
            jid = payload.get("jid")
            if jid:
                REVOKED_TOKEN_JIDS.add(jid)
    except Exception:
        pass


async def get_current_user_optional(
    request: Request,
    authorization: Optional[str] = Header(None),
    codeguardian_session: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Extracts authenticated User from Authorization header or Cookie if present;
    returns None if unauthenticated without raising.
    """
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif codeguardian_session:
        token = codeguardian_session.strip()

    if not token:
        return None

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None

        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        return result.scalars().first()
    except HTTPException:
        return None


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    codeguardian_session: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Strict FastAPI dependency ensuring the caller has a valid, active user session.
    """
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif codeguardian_session:
        token = codeguardian_session.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject identity.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with this token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
