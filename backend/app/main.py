import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.database import check_db_connection
from app.routers import (
    admin_router,
    ai_router,
    announcements_router,
    assignments_router,
    auth_router,
    courses_router,
    discussions_router,
    enrollments_router,
    health_router,
    instructor_router,
    lessons_router,
    materials_router,
    notifications_router,
    quizzes_router,
    student_router,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure local persistent data directory exists
    settings.resolved_data_dir
    settings.resolved_upload_dir
    check_db_connection()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for EduVerse - AI-Powered Learning Management System",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Configure CORS for local frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Enforce defensive HTTP security headers on all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler to prevent internal tracebacks or
    database schema disclosure in unhandled 500 responses.
    """
    logging.getLogger("uvicorn.error").error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please contact system support."},
    )

# Top-level Health Check (e.g. GET /health)
app.include_router(health_router, prefix="", tags=["Health & System"])

# API Version 1 Routers
api_v1_prefix = settings.API_V1_PREFIX  # /api/v1
app.include_router(health_router, prefix=api_v1_prefix)
app.include_router(auth_router, prefix=api_v1_prefix)
app.include_router(courses_router, prefix=api_v1_prefix)
app.include_router(enrollments_router, prefix=api_v1_prefix)
app.include_router(lessons_router, prefix=api_v1_prefix)
app.include_router(quizzes_router, prefix=api_v1_prefix)
app.include_router(assignments_router, prefix=api_v1_prefix)
app.include_router(materials_router, prefix=api_v1_prefix)
app.include_router(student_router, prefix=api_v1_prefix)
app.include_router(announcements_router, prefix=api_v1_prefix)
app.include_router(discussions_router, prefix=api_v1_prefix)
app.include_router(notifications_router, prefix=api_v1_prefix)
app.include_router(instructor_router, prefix=api_v1_prefix)
app.include_router(admin_router, prefix=api_v1_prefix)
app.include_router(ai_router, prefix=api_v1_prefix)


@app.get("/", tags=["Root"])
def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
        "documentation": "/docs",
        "health": "/health",
        "api_v1": settings.API_V1_PREFIX,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
    )
