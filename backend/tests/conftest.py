import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

# Configure isolated test SQLite and MongoDB databases before importing app settings
TEST_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "test_eduverse.db"
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["MONGODB_DATABASE"] = "eduverse_test"

from app.config import get_settings  # noqa: E402
get_settings.cache_clear()

from app.database import Base, engine, SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.mongo_schema import (  # noqa: E402
    COUNTERS_COLLECTION,
    ensure_mongo_collections_and_indexes,
)
from app.mongodb import close_mongo_client, get_mongo_database  # noqa: E402
from app.repositories.ai_repository import sync_sqlite_ai_to_mongo  # noqa: E402
from app.repositories.assignment_repository import sync_sqlite_assignments_to_mongo  # noqa: E402
from app.repositories.communication_repository import sync_sqlite_communications_to_mongo  # noqa: E402
from app.repositories.course_repository import sync_sqlite_learning_content_to_mongo  # noqa: E402
from app.repositories.instructor_ai_repository import sync_sqlite_instructor_ai_to_mongo  # noqa: E402
from app.repositories.material_repository import sync_sqlite_materials_to_mongo  # noqa: E402
from app.repositories.quiz_repository import sync_sqlite_quizzes_to_mongo  # noqa: E402
from app.repositories.user_repository import sync_sqlite_users_to_mongo  # noqa: E402
from app.utils.seed_data import seed_database  # noqa: E402


TEST_MONGO_COLLECTIONS = (
    "users",
    "instructor_profiles",
    "instructor_password_tokens",
    "courses",
    "course_sections",
    "lessons",
    "lesson_progress",
    "course_enrollments",
    "email_deliveries",
    "quizzes",
    "questions",
    "answer_options",
    "quiz_attempts",
    "quiz_attempt_answers",
    "assignments",
    "assignment_submissions",
    "learning_materials",
    "course_announcements",
    "course_discussions",
    "discussion_replies",
    "notifications",
    "ai_conversations",
    "ai_messages",
    "ai_quizzes",
    "ai_quiz_questions",
    "ai_quiz_options",
    "ai_quiz_attempts",
    "ai_quiz_answers",
    "study_preferences",
    "study_plans",
    "study_deadlines",
    "study_tasks",
    "study_notifications",
    "assignment_rubrics",
    "evaluation_criterion_rubrics",
    "assignment_evaluations",
    "assignment_evaluation_criteria",
    "instructor_question_papers",
    "instructor_generated_questions",
    COUNTERS_COLLECTION,
)


def _assert_test_mongo_database(settings) -> None:
    assert settings.MONGODB_DATABASE == "eduverse_test", (
        "Refusing MongoDB test setup or cleanup unless MONGODB_DATABASE is 'eduverse_test'."
    )
    assert settings.MONGODB_DATABASE != "eduverse", (
        "Tests must never modify the live 'eduverse' database."
    )


def _clear_test_mongo_database(settings) -> None:
    _assert_test_mongo_database(settings)
    cleanup_client = MongoClient(
        settings.MONGODB_URL,
        serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
        connectTimeoutMS=settings.MONGODB_CONNECT_TIMEOUT_MS,
        retryWrites=True,
    )
    try:
        cleanup_client.admin.command("ping")
        cleanup_db = cleanup_client[settings.MONGODB_DATABASE.strip()]
        assert cleanup_db.name == "eduverse_test", (
            "Refusing MongoDB cleanup outside the isolated 'eduverse_test' database."
        )

        collection_names = set(TEST_MONGO_COLLECTIONS)
        collection_names.update(cleanup_db.list_collection_names())
        for coll_name in sorted(collection_names):
            cleanup_db[coll_name].delete_many({})

        remaining_documents = {}
        for coll_name in cleanup_db.list_collection_names():
            document_count = cleanup_db[coll_name].count_documents({})
            if document_count:
                remaining_documents[coll_name] = document_count
        if remaining_documents:
            raise RuntimeError(
                f"MongoDB test cleanup left documents in eduverse_test: {remaining_documents}"
            )
    finally:
        cleanup_client.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create test tables/collections in isolated test SQLite and MongoDB DBs and seed baseline data."""
    settings = get_settings()
    _assert_test_mongo_database(settings)

    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink(missing_ok=True)

    Base.metadata.create_all(bind=engine)
    seed_database()

    mongo_db = get_mongo_database(settings)
    assert mongo_db.name == "eduverse_test"
    for coll_name in TEST_MONGO_COLLECTIONS:
        mongo_db[coll_name].delete_many({})
    ensure_mongo_collections_and_indexes(mongo_db, initialize_counters=True)
    sql_session = SessionLocal()
    try:
        sync_sqlite_users_to_mongo(sql_session, mongo_db)
        sync_sqlite_learning_content_to_mongo(sql_session, mongo_db)
        sync_sqlite_quizzes_to_mongo(sql_session, mongo_db)
        sync_sqlite_assignments_to_mongo(sql_session, mongo_db)
        sync_sqlite_materials_to_mongo(sql_session, mongo_db)
        sync_sqlite_communications_to_mongo(sql_session, mongo_db)
        sync_sqlite_ai_to_mongo(sql_session, mongo_db)
        sync_sqlite_instructor_ai_to_mongo(sql_session, mongo_db)
    finally:
        sql_session.close()

    yield

    try:
        _clear_test_mongo_database(settings)
    finally:
        close_mongo_client()
        try:
            Base.metadata.drop_all(bind=engine)
        finally:
            engine.dispose()
            if TEST_DB_PATH.exists():
                TEST_DB_PATH.unlink(missing_ok=True)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
