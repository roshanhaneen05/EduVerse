from datetime import datetime, timezone
from fastapi import APIRouter, status
from app.config import get_settings
from app.database import check_db_connection
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health & System"])
settings = get_settings()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Service Health Check",
    description="Check the operational status of the EduVerse API and its database connection.",
)
def get_health() -> HealthResponse:
    db_connected = check_db_connection()
    return HealthResponse(
        status="healthy" if db_connected else "degraded",
        project=settings.PROJECT_NAME,
        version="0.1.0",
        environment=settings.ENVIRONMENT,
        database="connected" if db_connected else "unavailable",
        timestamp=datetime.now(timezone.utc),
    )

