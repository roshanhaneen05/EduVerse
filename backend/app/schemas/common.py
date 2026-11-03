from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Application operational status")
    project: str = Field(default="EduVerse", description="Project name")
    version: str = Field(default="0.1.0", description="API version")
    environment: str = Field(default="development", description="Current running environment")
    database: str = Field(default="connected", description="Database connection status")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the health check",
    )


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None

