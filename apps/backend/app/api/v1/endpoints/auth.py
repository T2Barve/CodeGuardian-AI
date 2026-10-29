from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.session import get_db
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
    TokenResponse,
    UserProfileResponse,
)
from app.security.auth import (
    ACCESS_TOKEN_EXPIRE_SECONDS,
    create_access_token,
    decode_access_token,
    get_current_user,
    hash_password,
    revoke_token,
    verify_password,
)
from app.utils.logging import get_logger

logger = get_logger("codeguardian.api.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_user_permissions(role: str) -> List[str]:
    """Returns permission capabilities based on assigned RBAC role."""
    base_permissions = [
        "repositories:read",
        "pull_requests:read",
        "findings:read",
        "reports:read",
        "agents:read",
        "scanners:read",
    ]
    if role in ["SECURITY_LEAD", "ADMIN"]:
        return base_permissions + [
            "repositories:write",
            "analysis:trigger",
            "remediation:approve",
            "remediation:reject",
            "policies:manage",
            "integrations:manage",
            "users:manage",
        ]
    elif role == "DEVELOPER":
        return base_permissions + [
            "analysis:trigger",
            "remediation:propose",
        ]
    return base_permissions


def _to_user_profile(user: User) -> UserProfileResponse:
    return UserProfileResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        avatar_url=user.avatar_url,
        role=user.role,
        permissions=_get_user_permissions(user.role),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and issue cryptographic JWT session token",
)
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # 1. Look up user by username or email
    stmt = select(User).where(
        or_(
            User.username.ilike(request.username.strip()),
            User.email.ilike(request.username.strip()),
        )
    )
    res = await db.execute(stmt)
    user = res.scalars().first()

    if not user:
        # Prevent user enumeration timing by running verify against dummy
        verify_password("dummy", hash_password("dummy"))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Verify password
    if not user.password_hash or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Generate signed access token
    token = create_access_token(user_id=user.id, username=user.username, role=user.role)

    # 4. Set HttpOnly secure session cookie
    response.set_cookie(
        key="codeguardian_session",
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=(settings.ENVIRONMENT == "production"),
    )

    # 5. Audit log
    audit_repo = AuditRepository(db)
    await audit_repo.record(
        actor=user.username,
        action="USER_LOGIN_SUCCESS",
        resource_type="user",
        resource_id=user.id,
        metadata_payload={"role": user.role},
    )

    return TokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_SECONDS,
        user=_to_user_profile(user),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new CodeGuardian AI user account",
)
async def register(
    request: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # Check if username or email already exists
    stmt = select(User).where(
        or_(
            User.username.ilike(request.username.strip()),
            User.email.ilike(request.email.strip()) if request.email else False,
        )
    )
    res = await db.execute(stmt)
    existing = res.scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this username or email already exists.",
        )

    # Hash password with PBKDF2-HMAC-SHA256
    pwd_hash = hash_password(request.password)

    # Determine assigned role (first registered user or dev default)
    user_count_res = await db.execute(select(User))
    total_users = len(user_count_res.scalars().all())
    assigned_role = "ADMIN" if total_users == 0 else (request.role or "DEVELOPER")

    new_user = User(
        username=request.username.strip(),
        email=request.email.strip() if request.email else None,
        password_hash=pwd_hash,
        role=assigned_role,
        avatar_url=f"https://api.dicebear.com/7.x/identicon/svg?seed={request.username.strip()}",
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    token = create_access_token(user_id=new_user.id, username=new_user.username, role=new_user.role)

    response.set_cookie(
        key="codeguardian_session",
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=(settings.ENVIRONMENT == "production"),
    )

    audit_repo = AuditRepository(db)
    await audit_repo.record(
        actor=new_user.username,
        action="USER_REGISTERED",
        resource_type="user",
        resource_id=new_user.id,
        metadata_payload={"role": new_user.role},
    )

    return TokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_SECONDS,
        user=_to_user_profile(new_user),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Revoke access token and invalidate user session",
)
async def logout(
    response: Response,
    authorization: Optional[str] = Header(None),
    codeguardian_session: Optional[str] = Cookie(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LogoutResponse:
    # 1. Identify token to revoke
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif codeguardian_session:
        token = codeguardian_session.strip()

    if token:
        revoke_token(token)

    # 2. Clear HttpOnly cookie
    response.delete_cookie(
        key="codeguardian_session",
        httponly=True,
        samesite="lax",
    )

    # 3. Audit log
    audit_repo = AuditRepository(db)
    await audit_repo.record(
        actor=current_user.username,
        action="USER_LOGOUT",
        resource_type="user",
        resource_id=current_user.id,
    )

    return LogoutResponse(
        status="logged_out",
        message=f"Session for user '{current_user.username}' has been revoked.",
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Retrieve current authenticated user profile and permissions",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    return _to_user_profile(current_user)
