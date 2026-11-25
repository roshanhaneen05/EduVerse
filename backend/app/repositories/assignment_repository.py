import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.assignment import Assignment, AssignmentSubmission
from app.mongo_schema import next_sequence_id, sync_counter
from app.repositories.user_repository import _ensure_utc

logger = logging.getLogger(__name__)


@dataclass
class MongoAssignment:
    id: int
    course_id: int
    section_id: Optional[int]
    title: str
    description: Optional[str]
    instructions: str
    max_marks: int
    due_date: Optional[datetime]
    is_published: bool
    is_closed: bool
    allow_resubmission: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoAssignment":
        now = datetime.now(timezone.utc)
        sec_id = doc.get("section_id")
        return cls(
            id=int(doc["id"]),
            course_id=int(doc["course_id"]),
            section_id=int(sec_id) if sec_id is not None else None,
            title=str(doc["title"]),
            description=doc.get("description"),
            instructions=str(doc["instructions"]),
            max_marks=int(doc.get("max_marks", 100)),
            due_date=_ensure_utc(doc.get("due_date")),
            is_published=bool(doc.get("is_published", False)),
            is_closed=bool(doc.get("is_closed", False)),
            allow_resubmission=bool(doc.get("allow_resubmission", True)),
            is_archived=bool(doc.get("is_archived", False)),
            created_at=_ensure_utc(doc.get("created_at")) or now,
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
        )


@dataclass
class MongoAssignmentSubmission:
    id: int
    assignment_id: int
    student_id: int
    submission_text: str
    attachments_json: Optional[str]
    status: str
    is_late: bool
    submitted_at: datetime
    updated_at: datetime
    grade: Optional[float]
    feedback: Optional[str]
    graded_by_id: Optional[int]
    graded_at: Optional[datetime]

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoAssignmentSubmission":
        now = datetime.now(timezone.utc)
        grade_val = doc.get("grade")
        graded_by = doc.get("graded_by_id")
        return cls(
            id=int(doc["id"]),
            assignment_id=int(doc["assignment_id"]),
            student_id=int(doc["student_id"]),
            submission_text=str(doc["submission_text"]),
            attachments_json=doc.get("attachments_json"),
            status=str(doc.get("status", "submitted")),
            is_late=bool(doc.get("is_late", False)),
            submitted_at=_ensure_utc(doc.get("submitted_at")) or now,
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
            grade=float(grade_val) if grade_val is not None else None,
            feedback=doc.get("feedback"),
            graded_by_id=int(graded_by) if graded_by is not None else None,
            graded_at=_ensure_utc(doc.get("graded_at")),
        )


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------


def get_assignment_by_id(
    mongo_db: Database,
    assignment_id: int,
) -> Optional[MongoAssignment]:
    doc = mongo_db["assignments"].find_one({"id": int(assignment_id)})
    return MongoAssignment.from_doc(doc) if doc else None


def list_assignments_for_course(
    mongo_db: Database,
    course_id: int,
    *,
    published_only: bool = False,
    exclude_archived: bool = False,
    sort_asc: bool = True,
) -> List[MongoAssignment]:
    filt: Dict[str, Any] = {"course_id": int(course_id)}
    if published_only:
        filt["is_published"] = True
    if exclude_archived:
        filt["is_archived"] = False
    direction = ASCENDING if sort_asc else DESCENDING
    cursor = mongo_db["assignments"].find(filt).sort("created_at", direction)
    return [MongoAssignment.from_doc(d) for d in cursor]


def count_assignments_by_course_ids(
    mongo_db: Database,
    course_ids: Iterable[int],
) -> Dict[int, int]:
    ids = [int(c) for c in course_ids]
    if not ids:
        return {}
    pipeline = [
        {"$match": {"course_id": {"$in": ids}}},
        {"$group": {"_id": "$course_id", "count": {"$sum": 1}}},
    ]
    return {
        int(row["_id"]): int(row["count"])
        for row in mongo_db["assignments"].aggregate(pipeline)
    }


def create_assignment_doc(
    mongo_db: Database,
    *,
    course_id: int,
    section_id: Optional[int],
    title: str,
    description: Optional[str],
    instructions: str,
    max_marks: int,
    due_date: Optional[datetime],
    is_published: bool,
    allow_resubmission: bool,
) -> MongoAssignment:
    now = datetime.now(timezone.utc)
    assignment_id = next_sequence_id(mongo_db, "assignments")
    doc = {
        "id": assignment_id,
        "course_id": int(course_id),
        "section_id": int(section_id) if section_id is not None else None,
        "title": title.strip(),
        "description": description.strip() if description else None,
        "instructions": instructions.strip(),
        "max_marks": int(max_marks),
        "due_date": _ensure_utc(due_date),
        "is_published": bool(is_published),
        "is_closed": False,
        "allow_resubmission": bool(allow_resubmission),
        "is_archived": False,
        "created_at": now,
        "updated_at": now,
    }
    mongo_db["assignments"].insert_one(doc)
    return MongoAssignment.from_doc(doc)


def update_assignment_doc(
    mongo_db: Database,
    assignment_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoAssignment]:
    payload = dict(updates)
    payload["updated_at"] = datetime.now(timezone.utc)
    doc = mongo_db["assignments"].find_one_and_update(
        {"id": int(assignment_id)},
        {"$set": payload},
        return_document=ReturnDocument.AFTER,
    )
    return MongoAssignment.from_doc(doc) if doc else None


def restore_assignment_snapshot(
    mongo_db: Database,
    prev: MongoAssignment,
) -> None:
    mongo_db["assignments"].update_one(
        {"id": prev.id},
        {
            "$set": {
                "course_id": prev.course_id,
                "section_id": prev.section_id,
                "title": prev.title,
                "description": prev.description,
                "instructions": prev.instructions,
                "max_marks": prev.max_marks,
                "due_date": prev.due_date,
                "is_published": prev.is_published,
                "is_closed": prev.is_closed,
                "allow_resubmission": prev.allow_resubmission,
                "is_archived": prev.is_archived,
                "created_at": prev.created_at,
                "updated_at": prev.updated_at,
            }
        },
        upsert=True,
    )


def delete_assignment_doc(mongo_db: Database, assignment_id: int) -> None:
    aid = int(assignment_id)
    rubric_ids = [
        int(doc["id"])
        for doc in mongo_db["assignment_rubrics"].find(
            {"assignment_id": aid},
            {"_id": 0, "id": 1},
        )
    ]
    evaluation_ids = [
        int(doc["id"])
        for doc in mongo_db["assignment_evaluations"].find(
            {"assignment_id": aid},
            {"_id": 0, "id": 1},
        )
    ]

    if evaluation_ids:
        mongo_db["assignment_evaluation_criteria"].delete_many(
            {"evaluation_id": {"$in": evaluation_ids}}
        )
    mongo_db["assignment_evaluations"].delete_many({"assignment_id": aid})

    if rubric_ids:
        mongo_db["evaluation_criterion_rubrics"].delete_many(
            {"rubric_id": {"$in": rubric_ids}}
        )
    mongo_db["assignment_rubrics"].delete_many({"assignment_id": aid})

    mongo_db["assignment_submissions"].delete_many({"assignment_id": aid})
    mongo_db["assignments"].delete_one({"id": aid})


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------


def get_submission_by_id(
    mongo_db: Database,
    submission_id: int,
) -> Optional[MongoAssignmentSubmission]:
    doc = mongo_db["assignment_submissions"].find_one({"id": int(submission_id)})
    return MongoAssignmentSubmission.from_doc(doc) if doc else None


def get_submission_by_assignment_and_student(
    mongo_db: Database,
    assignment_id: int,
    student_id: int,
) -> Optional[MongoAssignmentSubmission]:
    doc = mongo_db["assignment_submissions"].find_one(
        {"assignment_id": int(assignment_id), "student_id": int(student_id)}
    )
    return MongoAssignmentSubmission.from_doc(doc) if doc else None


def list_submissions_for_assignment(
    mongo_db: Database,
    assignment_id: int,
) -> List[MongoAssignmentSubmission]:
    cursor = (
        mongo_db["assignment_submissions"]
        .find({"assignment_id": int(assignment_id)})
        .sort("submitted_at", DESCENDING)
    )
    return [MongoAssignmentSubmission.from_doc(d) for d in cursor]


def list_submissions_for_student_assignments(
    mongo_db: Database,
    student_id: int,
    assignment_ids: Iterable[int],
) -> Dict[int, MongoAssignmentSubmission]:
    ids = [int(a) for a in assignment_ids]
    if not ids:
        return {}
    cursor = mongo_db["assignment_submissions"].find(
        {"student_id": int(student_id), "assignment_id": {"$in": ids}}
    )
    return {
        int(doc["assignment_id"]): MongoAssignmentSubmission.from_doc(doc)
        for doc in cursor
    }


def count_submissions_stats_for_assignments(
    mongo_db: Database,
    assignment_ids: Iterable[int],
) -> Dict[int, Tuple[int, int]]:
    """Return {assignment_id: (submission_count, graded_count)}."""
    ids = [int(a) for a in assignment_ids]
    if not ids:
        return {}
    pipeline = [
        {"$match": {"assignment_id": {"$in": ids}}},
        {
            "$group": {
                "_id": "$assignment_id",
                "total": {"$sum": 1},
                "graded": {
                    "$sum": {
                        "$cond": [{"$ne": ["$grade", None]}, 1, 0]
                    }
                },
            }
        },
    ]
    return {
        int(row["_id"]): (int(row["total"]), int(row["graded"]))
        for row in mongo_db["assignment_submissions"].aggregate(pipeline)
    }


def list_assignments_by_course_ids(
    mongo_db: Database,
    course_ids: Iterable[int],
    *,
    published_only: bool = False,
    exclude_archived: bool = False,
) -> List[MongoAssignment]:
    ids = [int(c) for c in course_ids]
    if not ids:
        return []
    filt: Dict[str, Any] = {"course_id": {"$in": ids}}
    if published_only:
        filt["is_published"] = True
    if exclude_archived:
        filt["is_archived"] = False
    cursor = mongo_db["assignments"].find(filt).sort([("due_date", ASCENDING), ("id", ASCENDING)])
    return [MongoAssignment.from_doc(d) for d in cursor]


def list_submissions_by_assignment_ids(
    mongo_db: Database,
    assignment_ids: Iterable[int],
    *,
    student_ids: Optional[Iterable[int]] = None,
) -> List[MongoAssignmentSubmission]:
    ids = [int(a) for a in assignment_ids]
    if not ids:
        return []
    filt: Dict[str, Any] = {"assignment_id": {"$in": ids}}
    if student_ids is not None:
        sids = [int(s) for s in student_ids]
        if not sids:
            return []
        filt["student_id"] = {"$in": sids}
    cursor = mongo_db["assignment_submissions"].find(filt).sort("submitted_at", DESCENDING)
    return [MongoAssignmentSubmission.from_doc(d) for d in cursor]


def count_all_assignments(mongo_db: Database) -> int:
    return int(mongo_db["assignments"].count_documents({}))


def count_all_submissions(mongo_db: Database) -> int:
    return int(mongo_db["assignment_submissions"].count_documents({}))


def create_submission_doc(
    mongo_db: Database,
    *,
    assignment_id: int,
    student_id: int,
    submission_text: str,
    attachments_json: Optional[str],
    is_late: bool,
    now: Optional[datetime] = None,
) -> MongoAssignmentSubmission:
    ts = now or datetime.now(timezone.utc)
    sub_id = next_sequence_id(mongo_db, "assignment_submissions")
    doc = {
        "id": sub_id,
        "assignment_id": int(assignment_id),
        "student_id": int(student_id),
        "submission_text": submission_text.strip(),
        "attachments_json": attachments_json,
        "status": "submitted",
        "is_late": bool(is_late),
        "submitted_at": ts,
        "updated_at": ts,
        "grade": None,
        "feedback": None,
        "graded_by_id": None,
        "graded_at": None,
    }
    try:
        mongo_db["assignment_submissions"].insert_one(doc)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A submission already exists for this assignment.",
        ) from exc
    return MongoAssignmentSubmission.from_doc(doc)


def update_submission_doc(
    mongo_db: Database,
    submission_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoAssignmentSubmission]:
    doc = mongo_db["assignment_submissions"].find_one_and_update(
        {"id": int(submission_id)},
        {"$set": dict(updates)},
        return_document=ReturnDocument.AFTER,
    )
    return MongoAssignmentSubmission.from_doc(doc) if doc else None


def restore_submission_snapshot(
    mongo_db: Database,
    prev: MongoAssignmentSubmission,
) -> None:
    mongo_db["assignment_submissions"].update_one(
        {"id": prev.id},
        {
            "$set": {
                "assignment_id": prev.assignment_id,
                "student_id": prev.student_id,
                "submission_text": prev.submission_text,
                "attachments_json": prev.attachments_json,
                "status": prev.status,
                "is_late": prev.is_late,
                "submitted_at": prev.submitted_at,
                "updated_at": prev.updated_at,
                "grade": prev.grade,
                "feedback": prev.feedback,
                "graded_by_id": prev.graded_by_id,
                "graded_at": prev.graded_at,
            }
        },
        upsert=True,
    )


def delete_submission_doc(mongo_db: Database, submission_id: int) -> None:
    mongo_db["assignment_submissions"].delete_one({"id": int(submission_id)})


# ---------------------------------------------------------------------------
# Transitional SQLite Shadow Sync
# ---------------------------------------------------------------------------


def sync_assignment_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    assignment: MongoAssignment,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(Assignment).filter(Assignment.id == assignment.id).first()
        if row is None:
            row = Assignment(
                id=assignment.id,
                course_id=assignment.course_id,
                section_id=assignment.section_id,
                title=assignment.title,
                description=assignment.description,
                instructions=assignment.instructions,
                max_marks=assignment.max_marks,
                due_date=assignment.due_date,
                is_published=assignment.is_published,
                is_closed=assignment.is_closed,
                allow_resubmission=assignment.allow_resubmission,
                is_archived=assignment.is_archived,
                created_at=assignment.created_at,
                updated_at=assignment.updated_at,
            )
            sqlite_db.add(row)
        else:
            row.course_id = assignment.course_id
            row.section_id = assignment.section_id
            row.title = assignment.title
            row.description = assignment.description
            row.instructions = assignment.instructions
            row.max_marks = assignment.max_marks
            row.due_date = assignment.due_date
            row.is_published = assignment.is_published
            row.is_closed = assignment.is_closed
            row.allow_resubmission = assignment.allow_resubmission
            row.is_archived = assignment.is_archived
            row.updated_at = assignment.updated_at
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error(
            "SQLite shadow sync failed for assignment_id=%s: %s",
            assignment.id,
            type(exc).__name__,
        )
        raise


def delete_assignment_from_sqlite_shadow(
    sqlite_db: Optional[Session],
    assignment_id: int,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if row is not None:
            sqlite_db.delete(row)
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error(
            "SQLite shadow delete failed for assignment_id=%s: %s",
            assignment_id,
            type(exc).__name__,
        )
        raise


def sync_submission_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    sub: MongoAssignmentSubmission,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = (
            sqlite_db.query(AssignmentSubmission)
            .filter(AssignmentSubmission.id == sub.id)
            .first()
        )
        if row is None:
            row = AssignmentSubmission(
                id=sub.id,
                assignment_id=sub.assignment_id,
                student_id=sub.student_id,
                submission_text=sub.submission_text,
                attachments_json=sub.attachments_json,
                status=sub.status,
                is_late=sub.is_late,
                submitted_at=sub.submitted_at,
                updated_at=sub.updated_at,
                grade=sub.grade,
                feedback=sub.feedback,
                graded_by_id=sub.graded_by_id,
                graded_at=sub.graded_at,
            )
            sqlite_db.add(row)
        else:
            row.submission_text = sub.submission_text
            row.attachments_json = sub.attachments_json
            row.status = sub.status
            row.is_late = sub.is_late
            row.updated_at = sub.updated_at
            row.grade = sub.grade
            row.feedback = sub.feedback
            row.graded_by_id = sub.graded_by_id
            row.graded_at = sub.graded_at
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error(
            "SQLite shadow sync failed for submission_id=%s: %s",
            sub.id,
            type(exc).__name__,
        )
        raise


def sync_sqlite_assignments_to_mongo(
    sqlite_db: Session,
    mongo_db: Database,
) -> Dict[str, int]:
    """Seed helper: copy SQLite assignments and submissions to MongoDB."""
    counts: Dict[str, int] = {}

    assignments = sqlite_db.query(Assignment).order_by(Assignment.id.asc()).all()
    max_aid = 0
    for a in assignments:
        doc = {
            "id": int(a.id),
            "course_id": int(a.course_id),
            "section_id": int(a.section_id) if a.section_id is not None else None,
            "title": a.title,
            "description": a.description,
            "instructions": a.instructions,
            "max_marks": int(a.max_marks),
            "due_date": _ensure_utc(a.due_date),
            "is_published": bool(a.is_published),
            "is_closed": bool(a.is_closed),
            "allow_resubmission": bool(a.allow_resubmission),
            "is_archived": bool(a.is_archived),
            "created_at": _ensure_utc(a.created_at) or datetime.now(timezone.utc),
            "updated_at": _ensure_utc(a.updated_at) or datetime.now(timezone.utc),
        }
        mongo_db["assignments"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        max_aid = max(max_aid, doc["id"])
    sync_counter(mongo_db, "assignments", max_aid)
    counts["assignments"] = len(assignments)

    subs = sqlite_db.query(AssignmentSubmission).order_by(AssignmentSubmission.id.asc()).all()
    max_sid = 0
    for s in subs:
        doc = {
            "id": int(s.id),
            "assignment_id": int(s.assignment_id),
            "student_id": int(s.student_id),
            "submission_text": s.submission_text,
            "attachments_json": s.attachments_json,
            "status": s.status,
            "is_late": bool(s.is_late),
            "submitted_at": _ensure_utc(s.submitted_at) or datetime.now(timezone.utc),
            "updated_at": _ensure_utc(s.updated_at) or datetime.now(timezone.utc),
            "grade": float(s.grade) if s.grade is not None else None,
            "feedback": s.feedback,
            "graded_by_id": int(s.graded_by_id) if s.graded_by_id is not None else None,
            "graded_at": _ensure_utc(s.graded_at),
        }
        mongo_db["assignment_submissions"].update_one(
            {"id": doc["id"]}, {"$set": doc}, upsert=True
        )
        max_sid = max(max_sid, doc["id"])
    sync_counter(mongo_db, "assignment_submissions", max_sid)
    counts["assignment_submissions"] = len(subs)

    return counts
