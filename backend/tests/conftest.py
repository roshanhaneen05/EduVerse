import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Configure test database URL
TEST_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "test_eduverse.db"
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"

from app.database import Base, engine, SessionLocal
from app.main import app
from app.utils.seed_data import seed_database


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create test tables cleanly in isolated test SQLite database and seed baseline data."""
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink(missing_ok=True)
        except Exception:
            pass

    Base.metadata.create_all(bind=engine)
    seed_database()

    yield

    Base.metadata.drop_all(bind=engine)
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink(missing_ok=True)
        except Exception:
            pass


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
