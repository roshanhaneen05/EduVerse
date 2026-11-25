import logging
import re
from typing import Generator, Optional, Tuple

from fastapi import HTTPException, status
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import (
    ConfigurationError,
    ConnectionFailure,
    OperationFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_mongo_client: Optional[MongoClient] = None
_mongo_url_loaded: Optional[str] = None


def _sanitize_mongo_error(error: Exception) -> str:
    """Strip any embedded credentials from exception strings before logging or returning."""
    message = str(error)
    return re.sub(r"://([^:@/\s]+):([^@/\s]+)@", "://***:***@", message)


def init_mongo_client(settings_override: Optional[Settings] = None) -> Optional[MongoClient]:
    """
    Initialize the shared synchronous PyMongo client and verify Atlas connectivity.
    Returns None cleanly when MONGODB_URL is not yet configured.
    """
    global _mongo_client, _mongo_url_loaded

    settings = settings_override or get_settings()
    mongo_url = settings.MONGODB_URL.strip()

    if not settings.has_mongo_config:
        logger.info("MONGODB_URL is not configured; skipping MongoDB client initialization.")
        return None

    if _mongo_client is not None and _mongo_url_loaded == mongo_url:
        return _mongo_client

    if _mongo_client is not None:
        close_mongo_client()

    try:
        client: MongoClient = MongoClient(
            mongo_url,
            serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
            connectTimeoutMS=settings.MONGODB_CONNECT_TIMEOUT_MS,
            retryWrites=True,
        )
        client.admin.command("ping")
        _mongo_client = client
        _mongo_url_loaded = mongo_url
        logger.info(
            "Connected to MongoDB database '%s'.",
            settings.MONGODB_DATABASE,
        )
        return _mongo_client
    except (
        ConfigurationError,
        ServerSelectionTimeoutError,
        ConnectionFailure,
        OperationFailure,
        PyMongoError,
    ) as exc:
        logger.error("MongoDB initialization failed: %s", _sanitize_mongo_error(exc))
        try:
            client.close()  # type: ignore[possibly-undefined]
        except Exception:
            pass
        _mongo_client = None
        _mongo_url_loaded = None
        return None


def close_mongo_client() -> None:
    """Close the shared PyMongo client cleanly on application shutdown."""
    global _mongo_client, _mongo_url_loaded
    if _mongo_client is not None:
        try:
            _mongo_client.close()
            logger.info("Closed MongoDB client connection.")
        except Exception as exc:
            logger.warning("Error closing MongoDB client: %s", _sanitize_mongo_error(exc))
        finally:
            _mongo_client = None
            _mongo_url_loaded = None


def get_mongo_client(settings_override: Optional[Settings] = None) -> MongoClient:
    """Return an active PyMongo client, initializing lazily if configured."""
    settings = settings_override or get_settings()
    if not settings.has_mongo_config:
        raise RuntimeError("MONGODB_URL is not configured in the backend environment.")

    client = _mongo_client or init_mongo_client(settings)
    if client is None:
        raise ConnectionFailure("Unable to connect to MongoDB Atlas.")
    return client


def get_mongo_database(settings_override: Optional[Settings] = None) -> Database:
    """Return the configured MongoDB database instance."""
    settings = settings_override or get_settings()
    client = get_mongo_client(settings)
    return client[settings.MONGODB_DATABASE.strip()]


def get_mongo_db() -> Generator[Database, None, None]:
    """FastAPI dependency providing the active MongoDB database instance."""
    try:
        db = get_mongo_database()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except PyMongoError as exc:
        logger.error("MongoDB connection error during request: %s", _sanitize_mongo_error(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB database is currently unavailable.",
        ) from exc
    yield db


def check_mongo_connection(settings_override: Optional[Settings] = None) -> Tuple[bool, str]:
    """
    Verify MongoDB Atlas reachability via admin ping.
    Returns (is_connected, status_label) where status_label is
    'connected', 'not_configured', or 'unavailable'.
    """
    settings = settings_override or get_settings()
    if not settings.has_mongo_config:
        return False, "not_configured"

    try:
        client = get_mongo_client(settings)
        client.admin.command("ping")
        return True, "connected"
    except (PyMongoError, RuntimeError) as exc:
        logger.warning("MongoDB health check failed: %s", _sanitize_mongo_error(exc))
        return False, "unavailable"
