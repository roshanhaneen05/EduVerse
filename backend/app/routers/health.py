from datetime import datetime, timezone
from fastapi import APIRouter, status
from app.config import get_settings
from app.database import check_db_connection
from app.mongodb import check_mongo_connection
from app.schemas.common import HealthResponse, MongoHealthResponse

router = APIRouter(tags=["Health & System"])
settings = get_settings()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Service Health Check",
    description="Check the operational status of the EduVerse API and its database connections.",
)
def get_health() -> HealthResponse:
    db_connected = check_db_connection()
    _, mongo_status = check_mongo_connection()
    return HealthResponse(
        status="healthy" if db_connected else "degraded",
        project=settings.PROJECT_NAME,
        version="0.1.0",
        environment=settings.ENVIRONMENT,
        database="connected" if db_connected else "unavailable",
        mongodb=mongo_status,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/health/mongodb",
    response_model=MongoHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="MongoDB Atlas Health Check",
    description="Verify connectivity to the configured MongoDB Atlas cluster.",
)
def get_mongodb_health() -> MongoHealthResponse:
    mongo_connected, mongo_status = check_mongo_connection()
    overall = (
        "healthy"
        if mongo_connected
        else ("not_configured" if mongo_status == "not_configured" else "degraded")
    )
    return MongoHealthResponse(
        status=overall,
        mongodb=mongo_status,
        database=settings.MONGODB_DATABASE,
        timestamp=datetime.now(timezone.utc),
    )

