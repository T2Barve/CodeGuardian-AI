from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Service health status")
    version: str = Field(..., description="Application version")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), 
        description="UTC probe timestamp"
    )
    environment: str = Field(..., description="Runtime environment")


class ReadinessResponse(BaseModel):
    status: str = Field(..., description="Overall readiness status ('ready' or 'not_ready')")
    database: str = Field(..., description="Database connectivity status")
    redis: str = Field(..., description="Redis broker connectivity status")
    error: Optional[str] = Field(default=None, description="Detailed diagnostic error if unready")
