"""
Idempotent SQLite-to-MongoDB Atlas migration script for EduVerse.

Usage (from backend/ directory):
    python scripts/migrate_sqlite_to_mongo.py --dry-run --destination-database eduverse_test
    python scripts/migrate_sqlite_to_mongo.py --execute --destination-database eduverse_test

The production database `eduverse` is always rejected by this script. Production
migrations require a separately documented and explicitly approved process.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pymongo.database import Database  # noqa: E402
from pymongo.errors import PyMongoError  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.mongo_schema import (  # noqa: E402
    COLLECTION_NAMES,
    COUNTERS_COLLECTION,
    ensure_mongo_collections_and_indexes,
    sync_counter,
)
from app.mongodb import _sanitize_mongo_error, close_mongo_client, get_mongo_database  # noqa: E402

logger = logging.getLogger("eduverse.migration")

REDACTED_FIELDS = frozenset({"password_hash", "token_hash"})
PRODUCTION_DATABASE = "eduverse"

# Explicit column type rules per table matching SQLAlchemy models
TABLE_COLUMN_TYPES: Dict[str, Dict[str, str]] = {
    "users": {
        "id": "int",
        "email": "str",
        "full_name": "str",
        "password_hash": "str",
        "role": "str",
        "is_active": "bool",
        "created_at": "datetime",
        "updated_at": "datetime",
    },
    "instructor_profiles": {
        "id": "int",
        "user_id": "int",
        "instructor_id": "str",
        "phone_number": "str",
        "qualification": "str",
        "department": "str",
        "subject_expertise": "str",
        "experience_years": "int",
        "profile_photo_url": "str",
        "registered_at": "datetime",
    },
    "instructor_password_tokens": {
        "id": "int",
        "user_id": "int",
        "token_hash": "str",
        "purpose": "str",
        "expires_at": "datetime",
        "used_at": "datetime",
        "created_at": "datetime",
    },
    "courses": {
        "id": "int",
        "title": "str",
        "description": "str",
        "category": "str",
        "difficulty": "str",
        "is_published": "bool",
        "instructor_id": "int",
        "created_at": "datetime",
        "updated_at": "datetime",
    },
    "course_sections": {
        "id": "int",
        "course_id": "int",
        "title": "str",
        "description": "str",
        "order_index": "int",
        "created_at": "datetime",
        "updated_at": "datetime",
    },
    "lessons": {
        "id": "int",
        "course_id": "int",
        "section_id": "int",
        "title": "str",
        "content": "str",
        "video_url": "str",
        "video_storage_key": "str",
        "order_index": "int",
        "created_at": "datetime",
        "updated_at": "datetime",
    },
    "lesson_progress": {
        "id": "int",
        "student_id": "int",
        "lesson_id": "int",
        "is_completed": "bool",
        "completed_at": "datetime",
        "updated_at": "datetime",
    },
    "course_enrollments": {
        "id": "int",
        "student_id": "int",
        "course_id": "int",
        "enrolled_at": "datetime",
        "completion_percentage": "float",
        "status": "str",
        "reviewed_at": "datetime",
        "reviewed_by_instructor_id": "int",
    },
    "email_deliveries": {
        "id": "int",
        "enrollment_id": "int",
        "event_type": "str",
        "recipient_email": "str",
        "status": "str",
        "attempts": "int",
        "last_error": "str",
        "created_at": "datetime",
        "updated_at": "datetime",
        "sent_at": "datetime",
    },
    "quizzes": {
        "id": "int",
        "course_id": "int",
        "section_id": "int",
        "lesson_id": "int",
        "title": "str",
        "description": "str",
        "passing_score": "int",
        "is_published": "bool",
        "time_limit_minutes": "int",
        "max_attempts": "int",
        "created_at": "datetime",
        "updated_at": "datetime",
    },
    "questions": {
        "id": "int",
        "quiz_id": "int",
        "question_text": "str",
        "order_index": "int",
        "points": "int",
    },
    "answer_options": {
        "id": "int",
        "question_id": "int",
        "option_text": "str",
        "is_correct": "bool",
        "order_index": "int",
    },
    "quiz_attempts": {
        "id": "int",
        "quiz_id": "int",
        "student_id": "int",
        "score": "float",
        "total_points": "int",
        "passed": "bool",
        "attempt_number": "int",
        "is_completed": "bool",
        "started_at": "datetime",
        "submitted_at": "datetime",
    },
    "quiz_attempt_answers": {
        "id": "int",
        "attempt_id": "int",
        "question_id": "int",
        "selected_option_id": "int",
        "is_correct": "bool",
        "awarded_points": "int",
    },
    "assignments": {
        "id": "int",
        "course_id": "int",
        "section_id": "int",
        "title": "str",
        "description": "str",
        "instructions": "str",
        "max_marks": "int",
        "due_date": "datetime",
        "is_published": "bool",
        "is_closed": "bool",
        "allow_resubmission": "bool",
        "is_archived": "bool",
        "created_at": "datetime",
        "updated_at": "datetime",
    },
    "assignment_submissions": {
        "id": "int",
        "assignment_id": "int",
        "student_id": "int",
        "submission_text": "str",
        "attachments_json": "str",
        "status": "str",
        "is_late": "bool",
        "submitted_at": "datetime",
        "updated_at": "datetime",
        "grade": "float",
        "feedback": "str",
        "graded_by_id": "int",
        "graded_at": "datetime",
    },
    "assignment_rubrics": {
        "id": "int",
        "assignment_id": "int",
        "expected_answer": "str",
        "updated_by_id": "int",
        "updated_at": "datetime",
    },
    "evaluation_criterion_rubrics": {
        "id": "int",
        "rubric_id": "int",
        "criterion_name": "str",
        "maximum_marks": "float",
        "description": "str",
        "guidelines": "str",
        "order_index": "int",
    },
    "assignment_evaluations": {
        "id": "int",
        "submission_id": "int",
        "assignment_id": "int",
        "student_id": "int",
        "instructor_id": "int",
        "source_hash": "str",
        "ai_suggested_marks": "float",
        "final_marks": "float",
        "ai_feedback": "str",
        "instructor_feedback": "str",
        "evaluation_status": "str",
        "created_at": "datetime",
        "approved_at": "datetime",
    },
    "assignment_evaluation_criteria": {
        "id": "int",
        "evaluation_id": "int",
        "criterion_name": "str",
        "maximum_marks": "float",
        "suggested_marks": "float",
        "final_marks": "float",
        "feedback": "str",
        "order_index": "int",
    },
    "instructor_question_papers": {
        "id": "int",
        "instructor_id": "int",
        "course_id": "int",
        "title": "str",
        "total_marks": "float",
        "duration_minutes": "int",
        "difficulty": "str",
        "section_ids_json": "json",
        "lesson_ids_json": "json",
        "exam_date": "date",
        "status": "str",
        "generation_hash": "str",
        "created_at": "datetime",
        "updated_at": "datetime",
        "published_at": "datetime",
    },
    "instructor_generated_questions": {
        "id": "int",
        "question_paper_id": "int",
        "question_text": "str",
        "question_type": "str",
        "difficulty": "str",
        "marks": "float",
        "options_json": "json",
        "correct_answer": "str",
        "explanation": "str",
        "question_order": "int",
    },
    "learning_materials": {
        "id": "int",
        "title": "str",
        "description": "str",
        "original_filename": "str",
        "storage_key": "str",
        "mime_type": "str",
        "file_size": "int",
        "uploader_id": "int",
        "course_id": "int",
        "section_id": "int",
        "lesson_id": "int",
        "created_at": "datetime",
        "updated_at": "datetime",
    },
    "course_announcements": {
        "id": "int",
        "course_id": "int",
        "instructor_id": "int",
        "title": "str",
        "content": "str",
        "is_published": "bool",
        "created_at": "datetime",
        "updated_at": "datetime",
    },
    "course_discussions": {
        "id": "int",
        "course_id": "int",
        "user_id": "int",
        "title": "str",
        "content": "str",
        "is_pinned": "bool",
        "is_deleted": "bool",
        "created_at": "datetime",
        "updated_at": "datetime",
    },
    "discussion_replies": {
        "id": "int",
        "thread_id": "int",
        "user_id": "int",
        "parent_reply_id": "int",
        "content": "str",
        "is_deleted": "bool",
        "created_at": "datetime",
        "updated_at": "datetime",
    },
    "notifications": {
        "id": "int",
        "user_id": "int",
        "title": "str",
        "message": "str",
        "notification_type": "str",
        "link_url": "str",
        "is_read": "bool",
        "created_at": "datetime",
    },
    "ai_conversations": {
        "id": "int",
        "user_id": "int",
        "course_id": "int",
        "title": "str",
        "created_at": "datetime",
        "updated_at": "datetime",
    },
    "ai_messages": {
        "id": "int",
        "conversation_id": "int",
        "role": "str",
        "content": "str",
        "created_at": "datetime",
    },
    "ai_quizzes": {
        "id": "int",
        "student_id": "int",
        "course_id": "int",
        "section_id": "int",
        "lesson_id": "int",
        "title": "str",
        "difficulty": "str",
        "question_type": "str",
        "question_count": "int",
        "created_at": "datetime",
    },
    "ai_quiz_questions": {
        "id": "int",
        "quiz_id": "int",
        "question_text": "str",
        "question_type": "str",
        "correct_answer": "str",
        "explanation": "str",
        "difficulty": "str",
        "points": "float",
        "order_index": "int",
    },
    "ai_quiz_options": {
        "id": "int",
        "question_id": "int",
        "option_text": "str",
        "is_correct": "bool",
        "order_index": "int",
    },
    "ai_quiz_attempts": {
        "id": "int",
        "quiz_id": "int",
        "student_id": "int",
        "started_at": "datetime",
        "submitted_at": "datetime",
        "total_points": "float",
        "awarded_points": "float",
        "percentage": "float",
        "duration_seconds": "int",
        "performance_level": "str",
        "review_requested_at": "datetime",
    },
    "ai_quiz_answers": {
        "id": "int",
        "attempt_id": "int",
        "question_id": "int",
        "selected_option_id": "int",
        "answer_text": "str",
        "is_correct": "bool",
        "awarded_points": "float",
        "automated_feedback": "str",
    },
    "study_preferences": {
        "id": "int",
        "student_id": "int",
        "selected_course_ids": "json",
        "deadlines_json": "json",
        "available_hours_per_day": "float",
        "preferred_time": "str",
        "time_zone": "str",
        "daily_duration_minutes": "int",
        "target_completion_date": "date",
        "updated_at": "datetime",
    },
    "study_plans": {
        "id": "int",
        "student_id": "int",
        "selected_course_ids": "json",
        "target_completion_date": "date",
        "available_hours_per_day": "float",
        "preferred_time": "str",
        "time_zone": "str",
        "daily_duration_minutes": "int",
        "recommendations_json": "json",
        "generation_mode": "str",
        "is_active": "bool",
        "generated_at": "datetime",
    },
    "study_deadlines": {
        "id": "int",
        "plan_id": "int",
        "student_id": "int",
        "course_id": "int",
        "title": "str",
        "deadline_type": "str",
        "due_at": "datetime",
    },
    "study_tasks": {
        "id": "int",
        "plan_id": "int",
        "student_id": "int",
        "course_id": "int",
        "section_id": "int",
        "lesson_id": "int",
        "starts_at": "datetime",
        "duration_minutes": "int",
        "priority": "str",
        "status": "str",
        "rationale": "str",
        "completed_at": "datetime",
        "created_at": "datetime",
    },
    "study_notifications": {
        "id": "int",
        "student_id": "int",
        "task_id": "int",
        "deadline_id": "int",
        "notification_key": "str",
        "notification_type": "str",
        "message": "str",
        "remind_at": "datetime",
        "is_read": "bool",
        "created_at": "datetime",
    },
}

# Foreign key references: table -> tuple of (column_name, target_table)
TABLE_FOREIGN_KEYS: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "instructor_profiles": (("user_id", "users"),),
    "instructor_password_tokens": (("user_id", "users"),),
    "courses": (("instructor_id", "users"),),
    "course_sections": (("course_id", "courses"),),
    "lessons": (("course_id", "courses"), ("section_id", "course_sections")),
    "lesson_progress": (("student_id", "users"), ("lesson_id", "lessons")),
    "course_enrollments": (
        ("student_id", "users"),
        ("course_id", "courses"),
        ("reviewed_by_instructor_id", "users"),
    ),
    "email_deliveries": (("enrollment_id", "course_enrollments"),),
    "quizzes": (
        ("course_id", "courses"),
        ("section_id", "course_sections"),
        ("lesson_id", "lessons"),
    ),
    "questions": (("quiz_id", "quizzes"),),
    "answer_options": (("question_id", "questions"),),
    "quiz_attempts": (("quiz_id", "quizzes"), ("student_id", "users")),
    "quiz_attempt_answers": (
        ("attempt_id", "quiz_attempts"),
        ("question_id", "questions"),
        ("selected_option_id", "answer_options"),
    ),
    "assignments": (("course_id", "courses"), ("section_id", "course_sections")),
    "assignment_submissions": (
        ("assignment_id", "assignments"),
        ("student_id", "users"),
        ("graded_by_id", "users"),
    ),
    "assignment_rubrics": (("assignment_id", "assignments"), ("updated_by_id", "users")),
    "evaluation_criterion_rubrics": (("rubric_id", "assignment_rubrics"),),
    "assignment_evaluations": (
        ("submission_id", "assignment_submissions"),
        ("assignment_id", "assignments"),
        ("student_id", "users"),
        ("instructor_id", "users"),
    ),
    "assignment_evaluation_criteria": (("evaluation_id", "assignment_evaluations"),),
    "instructor_question_papers": (("instructor_id", "users"), ("course_id", "courses")),
    "instructor_generated_questions": (("question_paper_id", "instructor_question_papers"),),
    "learning_materials": (
        ("uploader_id", "users"),
        ("course_id", "courses"),
        ("section_id", "course_sections"),
        ("lesson_id", "lessons"),
    ),
    "course_announcements": (("course_id", "courses"), ("instructor_id", "users")),
    "course_discussions": (("course_id", "courses"), ("user_id", "users")),
    "discussion_replies": (
        ("thread_id", "course_discussions"),
        ("user_id", "users"),
        ("parent_reply_id", "discussion_replies"),
    ),
    "notifications": (("user_id", "users"),),
    "ai_conversations": (("user_id", "users"), ("course_id", "courses")),
    "ai_messages": (("conversation_id", "ai_conversations"),),
    "ai_quizzes": (
        ("student_id", "users"),
        ("course_id", "courses"),
        ("section_id", "course_sections"),
        ("lesson_id", "lessons"),
    ),
    "ai_quiz_questions": (("quiz_id", "ai_quizzes"),),
    "ai_quiz_options": (("question_id", "ai_quiz_questions"),),
    "ai_quiz_attempts": (("quiz_id", "ai_quizzes"), ("student_id", "users")),
    "ai_quiz_answers": (
        ("attempt_id", "ai_quiz_attempts"),
        ("question_id", "ai_quiz_questions"),
        ("selected_option_id", "ai_quiz_options"),
    ),
    "study_preferences": (("student_id", "users"),),
    "study_plans": (("student_id", "users"),),
    "study_deadlines": (
        ("plan_id", "study_plans"),
        ("student_id", "users"),
        ("course_id", "courses"),
    ),
    "study_tasks": (
        ("plan_id", "study_plans"),
        ("student_id", "users"),
        ("course_id", "courses"),
        ("section_id", "course_sections"),
        ("lesson_id", "lessons"),
    ),
    "study_notifications": (
        ("student_id", "users"),
        ("task_id", "study_tasks"),
        ("deadline_id", "study_deadlines"),
    ),
}


@dataclass
class TableMigrationStats:
    table: str
    source_count: int = 0
    target_before_count: int = 0
    target_after_count: int = 0
    would_insert: int = 0
    would_update: int = 0
    unchanged: int = 0
    inserted: int = 0
    updated: int = 0
    preview_records: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class MigrationReport:
    mode: str
    sqlite_path: str
    mongo_database: str
    backup_path: Optional[str] = None
    tables: List[TableMigrationStats] = field(default_factory=list)
    conversion_errors: List[str] = field(default_factory=list)
    integrity_errors: List[str] = field(default_factory=list)
    count_mismatches: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.conversion_errors or self.integrity_errors or self.count_mismatches)


def parse_sqlite_datetime(value: Any) -> Optional[datetime]:
    """Convert a SQLite datetime string or datetime object into UTC-aware datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    else:
        raise ValueError(f"Unsupported datetime value type: {type(value).__name__}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def parse_sqlite_date(value: Any) -> Optional[str]:
    """Convert a SQLite DATE value into an unambiguous ISO YYYY-MM-DD string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return date.fromisoformat(text[:10]).isoformat()
    raise ValueError(f"Unsupported date value type: {type(value).__name__}")


def parse_sqlite_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(int(value))
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("1", "true", "yes"):
            return True
        if low in ("0", "false", "no"):
            return False
    raise ValueError(f"Unsupported boolean value: {value!r}")


def parse_sqlite_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        return json.loads(text)
    raise ValueError(f"Unsupported JSON value type: {type(value).__name__}")


def convert_row_to_document(table_name: str, row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a SQLite row into a MongoDB-compatible dictionary preserving types and IDs."""
    col_types = TABLE_COLUMN_TYPES[table_name]
    doc: Dict[str, Any] = {}
    for col_name in row.keys():
        raw_val = row[col_name]
        expected_type = col_types.get(col_name, "str")
        if raw_val is None:
            doc[col_name] = None
            continue
        if expected_type == "int":
            doc[col_name] = int(raw_val)
        elif expected_type == "float":
            doc[col_name] = float(raw_val)
        elif expected_type == "bool":
            doc[col_name] = parse_sqlite_bool(raw_val)
        elif expected_type == "datetime":
            doc[col_name] = parse_sqlite_datetime(raw_val)
        elif expected_type == "date":
            doc[col_name] = parse_sqlite_date(raw_val)
        elif expected_type == "json":
            doc[col_name] = parse_sqlite_json(raw_val)
        else:
            doc[col_name] = str(raw_val)
    return doc


def redact_document_for_preview(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Produce a safe preview representation without exposing password/token hashes."""
    preview: Dict[str, Any] = {}
    for key, val in doc.items():
        if key in REDACTED_FIELDS:
            preview[key] = "<REDACTED>"
        elif isinstance(val, datetime):
            preview[key] = val.isoformat()
        elif isinstance(val, str) and len(val) > 120:
            preview[key] = val[:117] + "..."
        else:
            preview[key] = val
    return preview


def _normalize_mongo_doc_for_compare(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize datetimes (UTC + BSON millisecond precision) when comparing source vs stored Mongo docs."""
    normalized: Dict[str, Any] = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if isinstance(v, datetime):
            dt = v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
            normalized[k] = dt.replace(microsecond=(dt.microsecond // 1000) * 1000)
        else:
            normalized[k] = v
    return normalized


def open_sqlite_readonly(sqlite_path: Path) -> sqlite3.Connection:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database file not found: {sqlite_path}")
    uri = f"file:{sqlite_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def backup_sqlite_file(sqlite_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"{sqlite_path.stem}_backup_{stamp}{sqlite_path.suffix}"
    shutil.copy2(sqlite_path, backup_path)
    return backup_path


def validate_referential_integrity(
    docs_by_table: Dict[str, List[Dict[str, Any]]],
    db: Optional[Database] = None,
) -> List[str]:
    """
    Verify all non-null foreign keys in `docs_by_table` resolve to a valid parent ID
    in either the migrated source batch or already-present MongoDB documents.
    """
    errors: List[str] = []
    known_ids: Dict[str, Set[int]] = {
        table: {int(d["id"]) for d in docs if "id" in d}
        for table, docs in docs_by_table.items()
    }

    if db is not None:
        existing_collections = set(db.list_collection_names())
        for table in COLLECTION_NAMES:
            if table in existing_collections:
                mongo_ids = {
                    int(d["id"])
                    for d in db[table].find({"id": {"$exists": True}}, {"_id": 0, "id": 1})
                }
                known_ids.setdefault(table, set()).update(mongo_ids)

    for table, fks in TABLE_FOREIGN_KEYS.items():
        for doc in docs_by_table.get(table, []):
            doc_id = doc.get("id")
            for fk_col, parent_table in fks:
                fk_val = doc.get(fk_col)
                if fk_val is None:
                    continue
                if int(fk_val) not in known_ids.get(parent_table, set()):
                    errors.append(
                        f"{table}(id={doc_id}).{fk_col}={fk_val} references missing {parent_table}(id={fk_val})"
                    )
    return errors


def run_migration(
    *,
    sqlite_path: Path,
    db: Database,
    dry_run: bool = True,
    backup_dir: Optional[Path] = None,
    preview_limit: int = 10,
) -> MigrationReport:
    if not dry_run and (db.name or "").casefold() == PRODUCTION_DATABASE:
        raise ValueError(
            "Refusing to execute migration against production database 'eduverse'."
        )

    settings = get_settings()
    report = MigrationReport(
        mode="DRY-RUN" if dry_run else "EXECUTE",
        sqlite_path=str(sqlite_path),
        mongo_database=db.name or settings.MONGODB_DATABASE,
    )

    conn = open_sqlite_readonly(sqlite_path)
    docs_by_table: Dict[str, List[Dict[str, Any]]] = {}

    try:
        cur = conn.cursor()
        existing_sqlite_tables = {
            row[0]
            for row in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            ).fetchall()
        }
        existing_mongo_collections = set(db.list_collection_names())

        # Step 1: Read & convert all source SQLite rows (read-only)
        for table in COLLECTION_NAMES:
            if table not in existing_sqlite_tables:
                report.conversion_errors.append(f"Expected SQLite table '{table}' is missing.")
                docs_by_table[table] = []
                continue

            rows = cur.execute(f'SELECT * FROM "{table}" ORDER BY id ASC;').fetchall()
            converted: List[Dict[str, Any]] = []
            for idx, row in enumerate(rows):
                try:
                    converted.append(convert_row_to_document(table, row))
                except Exception as exc:
                    row_id = row["id"] if "id" in row.keys() else f"row#{idx}"
                    report.conversion_errors.append(
                        f"Conversion failed for {table}(id={row_id}): {exc}"
                    )
            docs_by_table[table] = converted

        # Step 2: Validate referential integrity before touching MongoDB
        report.integrity_errors.extend(validate_referential_integrity(docs_by_table, db=db))

        # Step 3: Backup SQLite file before live writes (never modify original)
        if not dry_run:
            if not report.ok:
                return report
            target_backup_dir = backup_dir or (sqlite_path.parent / "backups")
            report.backup_path = str(backup_sqlite_file(sqlite_path, target_backup_dir))
            ensure_mongo_collections_and_indexes(db, initialize_counters=False)
            existing_mongo_collections = set(db.list_collection_names())

        # Step 4: Inspect target diff / perform idempotent upserts
        for table in COLLECTION_NAMES:
            src_docs = docs_by_table.get(table, [])
            stats = TableMigrationStats(table=table, source_count=len(src_docs))

            if table in existing_mongo_collections:
                stats.target_before_count = int(db[table].count_documents({}))
                existing_by_id: Dict[int, Dict[str, Any]] = {
                    int(d["id"]): _normalize_mongo_doc_for_compare(d)
                    for d in db[table].find({"id": {"$exists": True}})
                }
            else:
                stats.target_before_count = 0
                existing_by_id = {}

            for doc in src_docs:
                doc_id = int(doc["id"])
                existing_doc = existing_by_id.get(doc_id)
                comparable_doc = _normalize_mongo_doc_for_compare(doc)
                if existing_doc is None:
                    action = "INSERT"
                    stats.would_insert += 1
                elif existing_doc != comparable_doc:
                    action = "UPDATE"
                    stats.would_update += 1
                else:
                    action = "UNCHANGED"
                    stats.unchanged += 1

                if len(stats.preview_records) < preview_limit:
                    stats.preview_records.append(
                        {
                            "action": action,
                            "record": redact_document_for_preview(doc),
                        }
                    )

                if not dry_run and action != "UNCHANGED":
                    res = db[table].update_one(
                        {"id": doc_id},
                        {"$set": doc},
                        upsert=True,
                    )
                    if res.upserted_id is not None:
                        stats.inserted += 1
                    elif res.modified_count > 0:
                        stats.updated += 1

            if not dry_run:
                max_id = max((int(d["id"]) for d in src_docs), default=0)
                sync_counter(db, table, max_id)
                stats.target_after_count = int(db[table].count_documents({}))
                if stats.target_after_count < stats.source_count:
                    report.count_mismatches.append(
                        f"{table}: source={stats.source_count}, target={stats.target_after_count}"
                    )
                # Verify every source ID is present in MongoDB
                src_ids = {int(d["id"]) for d in src_docs}
                if src_ids:
                    present_ids = {
                        int(d["id"])
                        for d in db[table].find({"id": {"$in": list(src_ids)}}, {"_id": 0, "id": 1})
                    }
                    missing_ids = sorted(src_ids - present_ids)
                    if missing_ids:
                        report.count_mismatches.append(
                            f"{table}: missing IDs in target: {missing_ids[:10]}"
                        )
            else:
                stats.target_after_count = stats.target_before_count

            report.tables.append(stats)

        # Post-migration MongoDB referential integrity check
        if not dry_run:
            mongo_docs: Dict[str, List[Dict[str, Any]]] = {
                table: list(db[table].find({}, {"_id": 0})) for table in COLLECTION_NAMES
            }
            post_fk_errors = validate_referential_integrity(mongo_docs, db=None)
            report.integrity_errors.extend(post_fk_errors)

        return report
    finally:
        conn.close()


def format_report(report: MigrationReport) -> str:
    lines: List[str] = []
    lines.append("=" * 84)
    lines.append(f"EduVerse SQLite -> MongoDB Migration Report [{report.mode}]")
    lines.append(f"Source SQLite : {report.sqlite_path}")
    lines.append(f"Target MongoDB: {report.mongo_database}")
    if report.backup_path:
        lines.append(f"SQLite Backup : {report.backup_path}")
    lines.append("=" * 84)
    lines.append(
        f"{'Collection':<32} | {'Src':>4} | {'TgtBefore':>9} | {'Ins':>4} | {'Upd':>4} | {'Same':>4} | {'TgtAfter':>8}"
    )
    lines.append("-" * 84)

    total_src = 0
    total_before = 0
    total_ins = 0
    total_upd = 0
    total_same = 0
    total_after = 0

    for t in report.tables:
        ins_val = t.would_insert if report.mode == "DRY-RUN" else t.inserted
        upd_val = t.would_update if report.mode == "DRY-RUN" else t.updated
        total_src += t.source_count
        total_before += t.target_before_count
        total_ins += ins_val
        total_upd += upd_val
        total_same += t.unchanged
        total_after += t.target_after_count
        lines.append(
            f"{t.table:<32} | {t.source_count:>4} | {t.target_before_count:>9} | "
            f"{ins_val:>4} | {upd_val:>4} | {t.unchanged:>4} | {t.target_after_count:>8}"
        )

    lines.append("-" * 84)
    lines.append(
        f"{'TOTAL (39 collections)':<32} | {total_src:>4} | {total_before:>9} | "
        f"{total_ins:>4} | {total_upd:>4} | {total_same:>4} | {total_after:>8}"
    )
    lines.append("=" * 84)

    previews = [(t.table, t.preview_records) for t in report.tables if t.preview_records]
    lines.append("\nRecord Previews (sensitive hashes redacted):")
    if not previews:
        lines.append("  (No records found in source tables.)")
    else:
        for table_name, records in previews:
            lines.append(f"  Collection: {table_name}")
            for item in records:
                lines.append(f"    [{item['action']}] {json.dumps(item['record'], default=str)}")

    lines.append("\nValidation Checks:")
    lines.append(f"  Conversion errors     : {len(report.conversion_errors)}")
    for err in report.conversion_errors:
        lines.append(f"    - {err}")
    lines.append(f"  Referential integrity : {len(report.integrity_errors)} issue(s)")
    for err in report.integrity_errors:
        lines.append(f"    - {err}")
    lines.append(f"  Count mismatches      : {len(report.count_mismatches)}")
    for err in report.count_mismatches:
        lines.append(f"    - {err}")
    lines.append(f"\nOverall Status: {'PASS' if report.ok else 'FAIL'}")
    return "\n".join(lines)


def validate_destination_database(destination_database: str) -> str:
    destination = destination_database.strip()
    if not destination:
        raise ValueError("An explicit MongoDB destination database is required.")
    if destination.casefold() == PRODUCTION_DATABASE:
        raise ValueError(
            "Refusing production database 'eduverse'. This script has no production override."
        )
    return destination


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate EduVerse SQLite data to MongoDB Atlas.")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect source/target and preview changes without modifying MongoDB.",
    )
    mode_group.add_argument(
        "--execute",
        action="store_true",
        help="Execute the idempotent migration against MongoDB Atlas.",
    )
    parser.add_argument(
        "--destination-database",
        required=True,
        help="Explicit non-production MongoDB database to inspect or migrate.",
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=BACKEND_DIR / "data" / "eduverse.db",
        help="Path to source SQLite database.",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        destination = validate_destination_database(args.destination_database)
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    settings = get_settings().model_copy(update={"MONGODB_DATABASE": destination})
    try:
        db = get_mongo_database(settings)
        if db.name.casefold() != destination.casefold():
            raise RuntimeError("Connected MongoDB database does not match the explicit destination.")
        report = run_migration(
            sqlite_path=args.sqlite_path,
            db=db,
            dry_run=not bool(args.execute),
        )
        print(format_report(report))
        return 0 if report.ok else 1
    except PyMongoError as exc:
        logger.error("MongoDB error during migration: %s", _sanitize_mongo_error(exc))
        return 2
    except Exception as exc:
        logger.error("Migration failed: %s", _sanitize_mongo_error(exc))
        return 2
    finally:
        close_mongo_client()


if __name__ == "__main__":
    raise SystemExit(main())
