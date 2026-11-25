from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Application operational status")
    project: str = Field(default="EduVerse", description="Project name")
    version: str = Field(default="0.1.0", description="API version")
    environment: str = Field(default="development", description="Current running environment")
    database: str = Field(default="connected", description="Primary database connection status")
    mongodb: str = Field(default="not_configured", description="MongoDB connection status")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the health check",
    )


class MongoHealthResponse(BaseModel):
    status: str = Field(description="MongoDB operational status (healthy, degraded, not_configured)")
    mongodb: str = Field(description="MongoDB connection status (connected, unavailable, not_configured)")
    database: str = Field(description="Configured MongoDB database name")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the MongoDB health check",
    )


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None

