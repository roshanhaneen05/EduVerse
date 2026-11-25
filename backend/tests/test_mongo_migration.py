import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.mongo_schema import COLLECTION_NAMES, COLLECTION_INDEXES
import scripts.migrate_sqlite_to_mongo as migration_script
from scripts.migrate_sqlite_to_mongo import (
    TABLE_COLUMN_TYPES,
    build_argument_parser,
    convert_row_to_document,
    parse_sqlite_bool,
    parse_sqlite_date,
    parse_sqlite_datetime,
    parse_sqlite_json,
    redact_document_for_preview,
    run_migration,
    validate_destination_database,
    validate_referential_integrity,
)


def test_all_39_collections_have_type_and_index_definitions():
    assert len(COLLECTION_NAMES) == 39
    assert set(TABLE_COLUMN_TYPES.keys()) == set(COLLECTION_NAMES)
    assert set(COLLECTION_INDEXES.keys()) == set(COLLECTION_NAMES)


def test_sqlite_type_converters():
    dt = parse_sqlite_datetime("2026-11-25 08:30:00")
    assert dt == datetime(2026, 11, 25, 8, 30, 0, tzinfo=timezone.utc)
    assert parse_sqlite_datetime("2026-11-25T08:30:00Z") == dt
    assert parse_sqlite_date("2026-11-25") == "2026-11-25"
    assert parse_sqlite_bool(1) is True
    assert parse_sqlite_bool(0) is False
    assert parse_sqlite_json("[1, 2, 3]") == [1, 2, 3]


def test_redact_document_hides_hashes():
    preview = redact_document_for_preview(
        {"id": 1, "email": "u@eduverse.io", "password_hash": "secret_hash", "token_hash": "tok"}
    )
    assert preview["password_hash"] == "<REDACTED>"
    assert preview["token_hash"] == "<REDACTED>"
    assert preview["email"] == "u@eduverse.io"


def test_migration_defaults_to_dry_run_and_requires_explicit_destination(monkeypatch):
    args = build_argument_parser().parse_args(["--destination-database", "eduverse_test"])
    assert args.execute is False
    assert args.dry_run is False

    with pytest.raises(SystemExit) as exc:
        build_argument_parser().parse_args(["--execute"])
    assert exc.value.code == 2
    assert validate_destination_database(" eduverse_test ") == "eduverse_test"

    mock_db = MagicMock()
    mock_db.name = "eduverse_test"
    run_options = {}
    monkeypatch.setattr(migration_script, "get_mongo_database", lambda _settings: mock_db)
    monkeypatch.setattr(
        migration_script,
        "run_migration",
        lambda **kwargs: run_options.update(kwargs) or MagicMock(ok=True),
    )
    monkeypatch.setattr(migration_script, "format_report", lambda _report: "mock dry-run report")
    monkeypatch.setattr(migration_script, "close_mongo_client", lambda: None)
    assert migration_script.main(["--destination-database", "eduverse_test"]) == 0
    assert run_options["dry_run"] is True


@pytest.mark.parametrize("destination", ["eduverse", "EDUVERSE", " eduverse "])
def test_migration_rejects_production_destination_before_connecting(destination, monkeypatch):
    def fail_if_connected(*_args, **_kwargs):
        raise AssertionError("MongoDB must not be contacted for the production destination.")

    monkeypatch.setattr(migration_script, "get_mongo_database", fail_if_connected)
    assert (
        migration_script.main(
            ["--execute", "--destination-database", destination]
        )
        == 2
    )


def test_run_migration_rejects_production_database_before_accessing_it():
    mock_db = MagicMock()
    mock_db.name = "eduverse"

    with pytest.raises(ValueError, match="production database"):
        run_migration(sqlite_path=Path("must-not-be-opened.db"), db=mock_db, dry_run=False)

    mock_db.list_collection_names.assert_not_called()
    mock_db.__getitem__.assert_not_called()


def test_validate_referential_integrity_detects_missing_fk():
    docs = {
        "users": [{"id": 1}],
        "courses": [{"id": 10, "instructor_id": 999}],
    }
    errors = validate_referential_integrity(docs, db=None)
    assert len(errors) == 1
    assert "courses(id=10).instructor_id=999" in errors[0]


def test_dry_run_makes_no_writes(tmp_path: Path):
    db_file = tmp_path / "mini.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    # Create minimal tables matching COLLECTION_NAMES
    cur.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, full_name TEXT, password_hash TEXT, role TEXT, is_active INTEGER, created_at TEXT, updated_at TEXT)"
    )
    cur.execute(
        "INSERT INTO users VALUES (1, 'a@eduverse.io', 'A', 'hash', 'admin', 1, '2026-11-25 08:00:00', '2026-11-25 08:00:00')"
    )
    for t in COLLECTION_NAMES:
        if t != "users":
            cur.execute(f'CREATE TABLE "{t}" (id INTEGER PRIMARY KEY)')
    conn.commit()
    conn.close()

    mock_db = MagicMock()
    mock_db.name = "eduverse"
    mock_db.list_collection_names.return_value = list(COLLECTION_NAMES)
    mock_coll = MagicMock()
    mock_coll.count_documents.return_value = 0
    mock_coll.find.return_value = []
    mock_db.__getitem__.return_value = mock_coll

    report = run_migration(sqlite_path=db_file, db=mock_db, dry_run=True)
    assert report.ok is True
    assert report.mode == "DRY-RUN"
    user_stats = next(t for t in report.tables if t.table == "users")
    assert user_stats.source_count == 1
    assert user_stats.would_insert == 1
    mock_coll.update_one.assert_not_called()
    mock_coll.insert_one.assert_not_called()
    mock_coll.delete_many.assert_not_called()


def test_dry_run_treats_bson_millisecond_datetimes_as_unchanged(tmp_path: Path):
    db_file = tmp_path / "mini2.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, full_name TEXT, password_hash TEXT, role TEXT, is_active INTEGER, created_at TEXT, updated_at TEXT)"
    )
    cur.execute(
        "INSERT INTO users VALUES (1, 'a@eduverse.io', 'A', 'hash', 'student', 1, '2026-11-22T16:49:18.576146+00:00', '2026-11-22T16:49:18.576146+00:00')"
    )
    for t in COLLECTION_NAMES:
        if t != "users":
            cur.execute(f'CREATE TABLE "{t}" (id INTEGER PRIMARY KEY)')
    conn.commit()
    conn.close()

    stored_dt = datetime(2026, 11, 22, 16, 49, 18, 576000)  # naive + ms-truncated as returned by PyMongo
    stored_doc = {
        "_id": "fake_oid",
        "id": 1,
        "email": "a@eduverse.io",
        "full_name": "A",
        "password_hash": "hash",
        "role": "student",
        "is_active": True,
        "created_at": stored_dt,
        "updated_at": stored_dt,
    }

    mock_db = MagicMock()
    mock_db.name = "eduverse"
    mock_db.list_collection_names.return_value = list(COLLECTION_NAMES)

    def _get_coll(name):
        coll = MagicMock()
        if name == "users":
            coll.count_documents.return_value = 1
            coll.find.return_value = [stored_doc]
        else:
            coll.count_documents.return_value = 0
            coll.find.return_value = []
        return coll

    mock_db.__getitem__.side_effect = _get_coll

    report = run_migration(sqlite_path=db_file, db=mock_db, dry_run=True)
    assert report.ok is True
    user_stats = next(t for t in report.tables if t.table == "users")
    assert user_stats.unchanged == 1
    assert user_stats.would_insert == 0
    assert user_stats.would_update == 0
