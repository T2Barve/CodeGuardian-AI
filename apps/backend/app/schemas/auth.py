from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username or email address", min_length=1)
    password: str = Field(..., description="Account password", min_length=1)


class RegisterRequest(BaseModel):
    username: str = Field(..., description="Unique alphanumeric username", min_length=3, max_length=50)
    password: str = Field(..., description="Account password", min_length=6, max_length=128)
    email: Optional[str] = Field(None, description="Contact email address")
    role: Optional[str] = Field("DEVELOPER", description="Platform role: DEVELOPER, SECURITY_LEAD, or ADMIN")


class UserProfileResponse(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    permissions: List[str] = Field(default_factory=list)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 86400
    user: UserProfileResponse


class LogoutResponse(BaseModel):
    status: str = "logged_out"
    message: str = "Session successfully invalidated."
