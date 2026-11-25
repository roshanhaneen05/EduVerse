from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pymongo.errors import ServerSelectionTimeoutError

from app.config import Settings, get_settings
from app.mongodb import (
    _sanitize_mongo_error,
    check_mongo_connection,
    close_mongo_client,
    get_mongo_db,
    init_mongo_client,
)


def test_settings_rejects_invalid_mongodb_url():
    with pytest.raises(ValueError, match="Invalid MONGODB_URL"):
        Settings(MONGODB_URL="http://invalid-scheme")


def test_settings_rejects_empty_mongodb_database():
    with pytest.raises(ValueError, match="Invalid MONGODB_DATABASE"):
        Settings(MONGODB_DATABASE="   ")


def test_sanitize_mongo_error_redacts_credentials():
    raw = "Auth failed for mongodb+srv://anusha:supersecret@cluster0.mongodb.net/"
    sanitized = _sanitize_mongo_error(Exception(raw))
    assert "supersecret" not in sanitized
    assert "anusha" not in sanitized
    assert "://***:***@" in sanitized


def test_check_mongo_connection_not_configured():
    cfg = Settings(MONGODB_URL="", MONGODB_DATABASE="eduverse_test")
    connected, status_label = check_mongo_connection(cfg)
    assert connected is False
    assert status_label == "not_configured"


def test_check_mongo_connection_placeholder_treated_as_not_configured():
    cfg = Settings(
        MONGODB_URL="mongodb+srv://YOUR_USERNAME:YOUR_PASSWORD@YOUR_CLUSTER.mongodb.net/eduverse_test?retryWrites=true&w=majority",
        MONGODB_DATABASE="eduverse_test",
    )
    connected, status_label = check_mongo_connection(cfg)
    assert connected is False
    assert status_label == "not_configured"


def test_init_and_close_mongo_client_success():
    close_mongo_client()
    cfg = Settings(
        MONGODB_URL="mongodb+srv://user:pass@cluster0.example.mongodb.net/",
        MONGODB_DATABASE="eduverse_test",
    )
    mock_client = MagicMock()
    mock_client.admin.command.return_value = {"ok": 1}

    with patch("app.mongodb.MongoClient", return_value=mock_client):
        client = init_mongo_client(cfg)
        assert client is mock_client
        mock_client.admin.command.assert_called_with("ping")

        connected, status_label = check_mongo_connection(cfg)
        assert connected is True
        assert status_label == "connected"

    close_mongo_client()
    mock_client.close.assert_called_once()


def test_init_mongo_client_handles_timeout_gracefully():
    close_mongo_client()
    cfg = Settings(
        MONGODB_URL="mongodb+srv://user:pass@cluster0.example.mongodb.net/",
        MONGODB_DATABASE="eduverse_test",
    )
    mock_client = MagicMock()
    mock_client.admin.command.side_effect = ServerSelectionTimeoutError("timed out")

    with patch("app.mongodb.MongoClient", return_value=mock_client):
        client = init_mongo_client(cfg)
        assert client is None
    close_mongo_client()


def test_get_mongo_db_raises_503_when_unconfigured():
    cfg = Settings(MONGODB_URL="", MONGODB_DATABASE="eduverse_test")
    with patch("app.mongodb.get_settings", return_value=cfg):
        gen = get_mongo_db()
        with pytest.raises(HTTPException) as exc_info:
            next(gen)
        assert exc_info.value.status_code == 503


def test_mongodb_health_endpoint(client):
    resp = client.get("/health/mongodb")
    assert resp.status_code == 200
    data = resp.json()
    assert data["database"] == get_settings().MONGODB_DATABASE
    assert data["mongodb"] in ("connected", "unavailable", "not_configured")
    assert data["status"] in ("healthy", "degraded", "not_configured")

    v1_resp = client.get("/api/v1/health/mongodb")
    assert v1_resp.status_code == 200
