import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson, LessonProgress
from app.models.section import CourseSection
from app.mongo_schema import next_sequence_id, sync_counter
from app.repositories.user_repository import _ensure_utc

logger = logging.getLogger(__name__)


@dataclass
class MongoCourse:
    id: int
    title: str
    description: str
    category: str
    difficulty: str
    is_published: bool
    instructor_id: int
    created_at: datetime
    updated_at: datetime

    @property
    def level(self) -> str:
        return self.difficulty

    @level.setter
    def level(self, value: str) -> None:
        self.difficulty = value

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoCourse":
        now = datetime.now(timezone.utc)
        return cls(
            id=int(doc["id"]),
            title=str(doc["title"]),
            description=str(doc["description"]),
            category=str(doc["category"]),
            difficulty=str(doc.get("difficulty", "Beginner")),
            is_published=bool(doc.get("is_published", False)),
            instructor_id=int(doc["instructor_id"]),
            created_at=_ensure_utc(doc.get("created_at")) or now,
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
        )


@dataclass
class MongoCourseSection:
    id: int
    course_id: int
    title: str
    description: Optional[str]
    order_index: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoCourseSection":
        now = datetime.now(timezone.utc)
        return cls(
            id=int(doc["id"]),
            course_id=int(doc["course_id"]),
            title=str(doc["title"]),
            description=doc.get("description"),
            order_index=int(doc.get("order_index", 1)),
            created_at=_ensure_utc(doc.get("created_at")) or now,
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
        )


@dataclass
class MongoLesson:
    id: int
    course_id: int
    section_id: Optional[int]
    title: str
    content: str
    video_url: Optional[str]
    video_storage_key: Optional[str]
    order_index: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoLesson":
        now = datetime.now(timezone.utc)
        sec_id = doc.get("section_id")
        return cls(
            id=int(doc["id"]),
            course_id=int(doc["course_id"]),
            section_id=int(sec_id) if sec_id is not None else None,
            title=str(doc["title"]),
            content=str(doc["content"]),
            video_url=doc.get("video_url"),
            video_storage_key=doc.get("video_storage_key"),
            order_index=int(doc.get("order_index", 1)),
            created_at=_ensure_utc(doc.get("created_at")) or now,
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
        )


@dataclass
class MongoLessonProgress:
    id: int
    student_id: int
    lesson_id: int
    is_completed: bool
    completed_at: Optional[datetime]
    updated_at: datetime

    @property
    def user_id(self) -> int:
        return self.student_id

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoLessonProgress":
        now = datetime.now(timezone.utc)
        return cls(
            id=int(doc["id"]),
            student_id=int(doc["student_id"]),
            lesson_id=int(doc["lesson_id"]),
            is_completed=bool(doc.get("is_completed", False)),
            completed_at=_ensure_utc(doc.get("completed_at")),
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
        )


@dataclass
class MongoCourseEnrollment:
    id: int
    student_id: int
    course_id: int
    enrolled_at: datetime
    completion_percentage: float
    status: str
    reviewed_at: Optional[datetime]
    reviewed_by_instructor_id: Optional[int]

    @property
    def user_id(self) -> int:
        return self.student_id

    @property
    def progress_percentage(self) -> float:
        return self.completion_percentage

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoCourseEnrollment":
        now = datetime.now(timezone.utc)
        rev_id = doc.get("reviewed_by_instructor_id")
        return cls(
            id=int(doc["id"]),
            student_id=int(doc["student_id"]),
            course_id=int(doc["course_id"]),
            enrolled_at=_ensure_utc(doc.get("enrolled_at")) or now,
            completion_percentage=float(doc.get("completion_percentage", 0.0)),
            status=str(doc.get("status", "pending")),
            reviewed_at=_ensure_utc(doc.get("reviewed_at")),
            reviewed_by_instructor_id=int(rev_id) if rev_id is not None else None,
        )


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------


def _build_course_filter(
    *,
    search: Optional[str] = None,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    is_published: Optional[bool] = None,
    instructor_id: Optional[int] = None,
    exact_category_and_difficulty: bool = False,
) -> Dict[str, Any]:
    filt: Dict[str, Any] = {}
    if is_published is not None:
        filt["is_published"] = bool(is_published)
    if instructor_id is not None:
        filt["instructor_id"] = int(instructor_id)
    if category:
        if exact_category_and_difficulty:
            filt["category"] = category
        else:
            filt["category"] = {"$regex": re.escape(category.strip()), "$options": "i"}
    if difficulty:
        if exact_category_and_difficulty:
            filt["difficulty"] = difficulty
        else:
            filt["difficulty"] = {"$regex": f"^{re.escape(difficulty.strip())}$", "$options": "i"}
    if search:
        pattern = re.escape(search.strip())
        or_clauses = [
            {"title": {"$regex": pattern, "$options": "i"}},
            {"description": {"$regex": pattern, "$options": "i"}},
        ]
        if not exact_category_and_difficulty:
            or_clauses.append({"category": {"$regex": pattern, "$options": "i"}})
        filt["$or"] = or_clauses
    return filt


def get_course_by_id(mongo_db: Database, course_id: int) -> Optional[MongoCourse]:
    doc = mongo_db["courses"].find_one({"id": int(course_id)})
    return MongoCourse.from_doc(doc) if doc else None


def list_courses_filtered(
    mongo_db: Database,
    *,
    search: Optional[str] = None,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    is_published: Optional[bool] = None,
    instructor_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[MongoCourse]:
    filt = _build_course_filter(
        search=search,
        category=category,
        difficulty=difficulty,
        is_published=is_published,
        instructor_id=instructor_id,
    )
    cursor = (
        mongo_db["courses"]
        .find(filt)
        .sort("created_at", DESCENDING)
        .skip(skip)
        .limit(limit)
    )
    return [MongoCourse.from_doc(d) for d in cursor]


def list_courses_paginated(
    mongo_db: Database,
    *,
    search: Optional[str] = None,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    is_published: Optional[bool] = None,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[int, List[MongoCourse]]:
    filt = _build_course_filter(
        search=search,
        category=category,
        difficulty=difficulty,
        is_published=is_published,
        exact_category_and_difficulty=True,
    )
    total = int(mongo_db["courses"].count_documents(filt))
    cursor = (
        mongo_db["courses"]
        .find(filt)
        .sort("created_at", DESCENDING)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    return total, [MongoCourse.from_doc(d) for d in cursor]


def get_distinct_course_categories(mongo_db: Database) -> List[str]:
    cats = mongo_db["courses"].distinct("category")
    return sorted([str(c) for c in cats if c])


def instructor_has_courses(mongo_db: Database, instructor_id: int) -> bool:
    return (
        mongo_db["courses"].find_one({"instructor_id": int(instructor_id)}, {"_id": 1})
        is not None
    )


def create_course_doc(
    mongo_db: Database,
    *,
    title: str,
    description: str,
    category: str,
    difficulty: str,
    is_published: bool,
    instructor_id: int,
) -> MongoCourse:
    now = datetime.now(timezone.utc)
    course_id = next_sequence_id(mongo_db, "courses")
    doc = {
        "id": course_id,
        "title": title.strip(),
        "description": description.strip(),
        "category": category.strip(),
        "difficulty": difficulty,
        "is_published": bool(is_published),
        "instructor_id": int(instructor_id),
        "created_at": now,
        "updated_at": now,
    }
    mongo_db["courses"].insert_one(doc)
    return MongoCourse.from_doc(doc)


def update_course_doc(
    mongo_db: Database,
    course_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoCourse]:
    payload = dict(updates)
    payload["updated_at"] = datetime.now(timezone.utc)
    doc = mongo_db["courses"].find_one_and_update(
        {"id": int(course_id)},
        {"$set": payload},
        return_document=ReturnDocument.AFTER,
    )
    return MongoCourse.from_doc(doc) if doc else None


def restore_course_snapshot(mongo_db: Database, prev: MongoCourse) -> None:
    mongo_db["courses"].update_one(
        {"id": prev.id},
        {
            "$set": {
                "title": prev.title,
                "description": prev.description,
                "category": prev.category,
                "difficulty": prev.difficulty,
                "is_published": prev.is_published,
                "instructor_id": prev.instructor_id,
                "updated_at": prev.updated_at,
            }
        },
        upsert=True,
    )


def delete_course_cascade_mongo(mongo_db: Database, course_id: int) -> None:
    from app.repositories.ai_repository import delete_ai_quiz_cascade_mongo
    from app.repositories.assignment_repository import delete_assignment_doc
    from app.repositories.instructor_ai_repository import delete_question_paper_cascade_mongo

    cid = int(course_id)
    mongo_db["ai_conversations"].update_many(
        {"course_id": cid},
        {"$set": {"course_id": None}},
    )

    ai_quiz_ids = [
        int(d["id"])
        for d in mongo_db["ai_quizzes"].find({"course_id": cid}, {"_id": 0, "id": 1})
    ]
    for ai_quiz_id in ai_quiz_ids:
        delete_ai_quiz_cascade_mongo(mongo_db, ai_quiz_id)

    question_paper_ids = [
        int(d["id"])
        for d in mongo_db["instructor_question_papers"].find(
            {"course_id": cid},
            {"_id": 0, "id": 1},
        )
    ]
    for paper_id in question_paper_ids:
        delete_question_paper_cascade_mongo(mongo_db, paper_id)

    study_deadline_ids = [
        int(d["id"])
        for d in mongo_db["study_deadlines"].find({"course_id": cid}, {"_id": 0, "id": 1})
    ]
    study_task_ids = [
        int(d["id"])
        for d in mongo_db["study_tasks"].find({"course_id": cid}, {"_id": 0, "id": 1})
    ]
    study_notification_refs = []
    if study_task_ids:
        study_notification_refs.append({"task_id": {"$in": study_task_ids}})
    if study_deadline_ids:
        study_notification_refs.append({"deadline_id": {"$in": study_deadline_ids}})
    if study_notification_refs:
        mongo_db["study_notifications"].delete_many({"$or": study_notification_refs})
    mongo_db["study_tasks"].delete_many({"course_id": cid})
    mongo_db["study_deadlines"].delete_many({"course_id": cid})
    mongo_db["study_preferences"].update_many(
        {"selected_course_ids": cid},
        {"$pull": {"selected_course_ids": cid}},
    )
    mongo_db["study_preferences"].update_many(
        {"deadlines_json.course_id": cid},
        {"$pull": {"deadlines_json": {"course_id": cid}}},
    )
    mongo_db["study_plans"].update_many(
        {"selected_course_ids": cid},
        {"$pull": {"selected_course_ids": cid}},
    )

    lesson_ids = [
        int(d["id"])
        for d in mongo_db["lessons"].find({"course_id": cid}, {"_id": 0, "id": 1})
    ]
    if lesson_ids:
        mongo_db["lesson_progress"].delete_many({"lesson_id": {"$in": lesson_ids}})
    mongo_db["lessons"].delete_many({"course_id": cid})
    mongo_db["course_sections"].delete_many({"course_id": cid})

    enrollment_ids = [
        int(d["id"])
        for d in mongo_db["course_enrollments"].find({"course_id": cid}, {"_id": 0, "id": 1})
    ]
    if enrollment_ids:
        mongo_db["email_deliveries"].delete_many({"enrollment_id": {"$in": enrollment_ids}})
    mongo_db["course_enrollments"].delete_many({"course_id": cid})

    quiz_ids = [
        int(d["id"])
        for d in mongo_db["quizzes"].find({"course_id": cid}, {"_id": 0, "id": 1})
    ]
    if quiz_ids:
        question_ids = [
            int(d["id"])
            for d in mongo_db["questions"].find({"quiz_id": {"$in": quiz_ids}}, {"_id": 0, "id": 1})
        ]
        if question_ids:
            mongo_db["answer_options"].delete_many({"question_id": {"$in": question_ids}})
            mongo_db["quiz_attempt_answers"].delete_many({"question_id": {"$in": question_ids}})
        mongo_db["questions"].delete_many({"quiz_id": {"$in": quiz_ids}})
        mongo_db["quiz_attempts"].update_many({"quiz_id": {"$in": quiz_ids}}, {"$set": {"quiz_id": None}})
    mongo_db["quizzes"].delete_many({"course_id": cid})

    assignment_ids = [
        int(d["id"])
        for d in mongo_db["assignments"].find({"course_id": cid}, {"_id": 0, "id": 1})
    ]
    for assignment_id in assignment_ids:
        delete_assignment_doc(mongo_db, assignment_id)

    mongo_db["learning_materials"].delete_many({"course_id": cid})
    mongo_db["course_announcements"].delete_many({"course_id": cid})

    thread_ids = [
        int(d["id"])
        for d in mongo_db["course_discussions"].find({"course_id": cid}, {"_id": 0, "id": 1})
    ]
    if thread_ids:
        mongo_db["discussion_replies"].delete_many({"thread_id": {"$in": thread_ids}})
    mongo_db["course_discussions"].delete_many({"course_id": cid})

    mongo_db["courses"].delete_one({"id": cid})


# ---------------------------------------------------------------------------
# Course Sections
# ---------------------------------------------------------------------------


def get_section_by_id(mongo_db: Database, section_id: int) -> Optional[MongoCourseSection]:
    doc = mongo_db["course_sections"].find_one({"id": int(section_id)})
    return MongoCourseSection.from_doc(doc) if doc else None


def list_all_courses(
    mongo_db: Database,
    *,
    instructor_id: Optional[int] = None,
    is_published: Optional[bool] = None,
    exclude_ids: Optional[Iterable[int]] = None,
) -> List[MongoCourse]:
    filt: Dict[str, Any] = {}
    if instructor_id is not None:
        filt["instructor_id"] = int(instructor_id)
    if is_published is not None:
        filt["is_published"] = bool(is_published)
    if exclude_ids is not None:
        ex_list = [int(c) for c in exclude_ids]
        if ex_list:
            filt["id"] = {"$nin": ex_list}
    cursor = mongo_db["courses"].find(filt).sort("created_at", DESCENDING)
    return [MongoCourse.from_doc(d) for d in cursor]


def get_courses_by_ids(
    mongo_db: Database,
    course_ids: Iterable[int],
) -> Dict[int, MongoCourse]:
    ids = [int(c) for c in course_ids]
    if not ids:
        return {}
    return {
        int(doc["id"]): MongoCourse.from_doc(doc)
        for doc in mongo_db["courses"].find({"id": {"$in": ids}})
    }


def list_sections_for_course(mongo_db: Database, course_id: int) -> List[MongoCourseSection]:
    cursor = (
        mongo_db["course_sections"]
        .find({"course_id": int(course_id)})
        .sort("order_index", ASCENDING)
    )
    return [MongoCourseSection.from_doc(d) for d in cursor]


def list_sections_by_course_ids(
    mongo_db: Database,
    course_ids: Iterable[int],
) -> List[MongoCourseSection]:
    ids = [int(c) for c in course_ids]
    if not ids:
        return []
    cursor = (
        mongo_db["course_sections"]
        .find({"course_id": {"$in": ids}})
        .sort([("course_id", ASCENDING), ("order_index", ASCENDING), ("id", ASCENDING)])
    )
    return [MongoCourseSection.from_doc(d) for d in cursor]


def create_section_doc(
    mongo_db: Database,
    *,
    course_id: int,
    title: str,
    description: Optional[str],
    order_index: int,
) -> MongoCourseSection:
    now = datetime.now(timezone.utc)
    sec_id = next_sequence_id(mongo_db, "course_sections")
    doc = {
        "id": sec_id,
        "course_id": int(course_id),
        "title": title.strip(),
        "description": description.strip() if description else None,
        "order_index": int(order_index),
        "created_at": now,
        "updated_at": now,
    }
    mongo_db["course_sections"].insert_one(doc)
    return MongoCourseSection.from_doc(doc)


def update_section_doc(
    mongo_db: Database,
    section_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoCourseSection]:
    payload = dict(updates)
    payload["updated_at"] = datetime.now(timezone.utc)
    doc = mongo_db["course_sections"].find_one_and_update(
        {"id": int(section_id)},
        {"$set": payload},
        return_document=ReturnDocument.AFTER,
    )
    return MongoCourseSection.from_doc(doc) if doc else None


def restore_section_snapshot(mongo_db: Database, prev: MongoCourseSection) -> None:
    mongo_db["course_sections"].update_one(
        {"id": prev.id},
        {
            "$set": {
                "course_id": prev.course_id,
                "title": prev.title,
                "description": prev.description,
                "order_index": prev.order_index,
                "created_at": prev.created_at,
                "updated_at": prev.updated_at,
            }
        },
        upsert=True,
    )


def delete_section_doc(mongo_db: Database, section_id: int) -> None:
    sid = int(section_id)
    mongo_db["quizzes"].update_many({"section_id": sid}, {"$set": {"section_id": None}})
    mongo_db["assignments"].update_many({"section_id": sid}, {"$set": {"section_id": None}})
    mongo_db["learning_materials"].update_many({"section_id": sid}, {"$set": {"section_id": None}})
    mongo_db["course_sections"].delete_one({"id": sid})


def reorder_sections_in_course(
    mongo_db: Database,
    course_id: int,
    order_map: Dict[int, int],
) -> None:
    now = datetime.now(timezone.utc)
    for sec_id, order_idx in order_map.items():
        mongo_db["course_sections"].update_one(
            {"id": int(sec_id), "course_id": int(course_id)},
            {"$set": {"order_index": int(order_idx), "updated_at": now}},
        )


# ---------------------------------------------------------------------------
# Lessons & Lesson Progress
# ---------------------------------------------------------------------------


def get_lesson_by_id(mongo_db: Database, lesson_id: int) -> Optional[MongoLesson]:
    doc = mongo_db["lessons"].find_one({"id": int(lesson_id)})
    return MongoLesson.from_doc(doc) if doc else None


def list_lessons_for_course(mongo_db: Database, course_id: int) -> List[MongoLesson]:
    cursor = (
        mongo_db["lessons"]
        .find({"course_id": int(course_id)})
        .sort("order_index", ASCENDING)
    )
    return [MongoLesson.from_doc(d) for d in cursor]


def get_adjacent_lesson_ids(
    mongo_db: Database,
    course_id: int,
    current_order_index: int,
) -> Tuple[Optional[int], Optional[int]]:
    prev_doc = mongo_db["lessons"].find_one(
        {"course_id": int(course_id), "order_index": {"$lt": int(current_order_index)}},
        sort=[("order_index", DESCENDING)],
        projection={"_id": 0, "id": 1},
    )
    next_doc = mongo_db["lessons"].find_one(
        {"course_id": int(course_id), "order_index": {"$gt": int(current_order_index)}},
        sort=[("order_index", ASCENDING)],
        projection={"_id": 0, "id": 1},
    )
    return (
        int(prev_doc["id"]) if prev_doc else None,
        int(next_doc["id"]) if next_doc else None,
    )


def count_lessons_for_section(mongo_db: Database, section_id: int) -> int:
    return int(mongo_db["lessons"].count_documents({"section_id": int(section_id)}))


def count_lessons_for_course(mongo_db: Database, course_id: int) -> int:
    return int(mongo_db["lessons"].count_documents({"course_id": int(course_id)}))


def count_lessons_by_course_ids(
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
    return {int(row["_id"]): int(row["count"]) for row in mongo_db["lessons"].aggregate(pipeline)}


def create_lesson_doc(
    mongo_db: Database,
    *,
    course_id: int,
    section_id: Optional[int],
    title: str,
    content: str,
    video_url: Optional[str],
    order_index: int,
    video_storage_key: Optional[str] = None,
) -> MongoLesson:
    now = datetime.now(timezone.utc)
    lesson_id = next_sequence_id(mongo_db, "lessons")
    doc = {
        "id": lesson_id,
        "course_id": int(course_id),
        "section_id": int(section_id) if section_id is not None else None,
        "title": title.strip(),
        "content": content.strip(),
        "video_url": video_url.strip() if video_url else None,
        "video_storage_key": video_storage_key,
        "order_index": int(order_index),
        "created_at": now,
        "updated_at": now,
    }
    mongo_db["lessons"].insert_one(doc)
    return MongoLesson.from_doc(doc)


def update_lesson_doc(
    mongo_db: Database,
    lesson_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoLesson]:
    payload = dict(updates)
    payload["updated_at"] = datetime.now(timezone.utc)
    doc = mongo_db["lessons"].find_one_and_update(
        {"id": int(lesson_id)},
        {"$set": payload},
        return_document=ReturnDocument.AFTER,
    )
    return MongoLesson.from_doc(doc) if doc else None


def restore_lesson_snapshot(mongo_db: Database, prev: MongoLesson) -> None:
    mongo_db["lessons"].update_one(
        {"id": prev.id},
        {
            "$set": {
                "course_id": prev.course_id,
                "section_id": prev.section_id,
                "title": prev.title,
                "content": prev.content,
                "video_url": prev.video_url,
                "video_storage_key": prev.video_storage_key,
                "order_index": prev.order_index,
                "created_at": prev.created_at,
                "updated_at": prev.updated_at,
            }
        },
        upsert=True,
    )


def delete_lesson_doc(mongo_db: Database, lesson_id: int) -> None:
    lid = int(lesson_id)
    mongo_db["lesson_progress"].delete_many({"lesson_id": lid})
    mongo_db["quizzes"].update_many({"lesson_id": lid}, {"$set": {"lesson_id": None}})
    mongo_db["learning_materials"].update_many({"lesson_id": lid}, {"$set": {"lesson_id": None}})
    mongo_db["lessons"].delete_one({"id": lid})


def reassign_lessons_section(
    mongo_db: Database,
    from_section_id: int,
    to_section_id: Optional[int],
) -> None:
    mongo_db["lessons"].update_many(
        {"section_id": int(from_section_id)},
        {
            "$set": {
                "section_id": int(to_section_id) if to_section_id is not None else None,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )


def get_lesson_progress(
    mongo_db: Database,
    student_id: int,
    lesson_id: int,
) -> Optional[MongoLessonProgress]:
    doc = mongo_db["lesson_progress"].find_one(
        {"student_id": int(student_id), "lesson_id": int(lesson_id)}
    )
    return MongoLessonProgress.from_doc(doc) if doc else None


def list_lessons_by_course_ids(
    mongo_db: Database,
    course_ids: Iterable[int],
) -> List[MongoLesson]:
    ids = [int(c) for c in course_ids]
    if not ids:
        return []
    cursor = (
        mongo_db["lessons"]
        .find({"course_id": {"$in": ids}})
        .sort([("course_id", ASCENDING), ("order_index", ASCENDING), ("id", ASCENDING)])
    )
    return [MongoLesson.from_doc(d) for d in cursor]


def get_lessons_by_ids(
    mongo_db: Database,
    lesson_ids: Iterable[int],
) -> Dict[int, MongoLesson]:
    ids = [int(l) for l in lesson_ids]
    if not ids:
        return {}
    return {
        int(doc["id"]): MongoLesson.from_doc(doc)
        for doc in mongo_db["lessons"].find({"id": {"$in": ids}})
    }


def list_lesson_progress(
    mongo_db: Database,
    *,
    student_id: Optional[int] = None,
    student_ids: Optional[Iterable[int]] = None,
    lesson_ids: Optional[Iterable[int]] = None,
    completed_only: bool = False,
) -> List[MongoLessonProgress]:
    filt: Dict[str, Any] = {}
    if student_id is not None:
        filt["student_id"] = int(student_id)
    elif student_ids is not None:
        sids = [int(s) for s in student_ids]
        if not sids:
            return []
        filt["student_id"] = {"$in": sids}
    if lesson_ids is not None:
        lids = [int(l) for l in lesson_ids]
        if not lids:
            return []
        filt["lesson_id"] = {"$in": lids}
    if completed_only:
        filt["is_completed"] = True
    cursor = mongo_db["lesson_progress"].find(filt)
    return [MongoLessonProgress.from_doc(d) for d in cursor]


def get_completed_lesson_ids(
    mongo_db: Database,
    student_id: int,
    lesson_ids: Optional[Iterable[int]] = None,
) -> Set[int]:
    filt: Dict[str, Any] = {"student_id": int(student_id), "is_completed": True}
    if lesson_ids is not None:
        id_list = [int(i) for i in lesson_ids]
        if not id_list:
            return set()
        filt["lesson_id"] = {"$in": id_list}
    return {
        int(d["lesson_id"])
        for d in mongo_db["lesson_progress"].find(filt, {"_id": 0, "lesson_id": 1})
    }


def upsert_lesson_progress(
    mongo_db: Database,
    *,
    student_id: int,
    lesson_id: int,
    is_completed: bool = True,
    now: Optional[datetime] = None,
) -> MongoLessonProgress:
    ts = now or datetime.now(timezone.utc)
    existing = get_lesson_progress(mongo_db, student_id, lesson_id)
    if existing:
        doc = mongo_db["lesson_progress"].find_one_and_update(
            {"id": existing.id},
            {
                "$set": {
                    "is_completed": bool(is_completed),
                    "completed_at": ts if is_completed else None,
                    "updated_at": ts,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return MongoLessonProgress.from_doc(doc)

    prog_id = next_sequence_id(mongo_db, "lesson_progress")
    doc = {
        "id": prog_id,
        "student_id": int(student_id),
        "lesson_id": int(lesson_id),
        "is_completed": bool(is_completed),
        "completed_at": ts if is_completed else None,
        "updated_at": ts,
    }
    try:
        mongo_db["lesson_progress"].insert_one(doc)
    except DuplicateKeyError:
        doc = mongo_db["lesson_progress"].find_one_and_update(
            {"student_id": int(student_id), "lesson_id": int(lesson_id)},
            {
                "$set": {
                    "is_completed": bool(is_completed),
                    "completed_at": ts if is_completed else None,
                    "updated_at": ts,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
    return MongoLessonProgress.from_doc(doc)


# ---------------------------------------------------------------------------
# Course Enrollments
# ---------------------------------------------------------------------------


def get_enrollment_by_id(
    mongo_db: Database,
    enrollment_id: int,
) -> Optional[MongoCourseEnrollment]:
    doc = mongo_db["course_enrollments"].find_one({"id": int(enrollment_id)})
    return MongoCourseEnrollment.from_doc(doc) if doc else None


def get_enrollment_by_student_and_course(
    mongo_db: Database,
    student_id: int,
    course_id: int,
) -> Optional[MongoCourseEnrollment]:
    doc = mongo_db["course_enrollments"].find_one(
        {"student_id": int(student_id), "course_id": int(course_id)}
    )
    return MongoCourseEnrollment.from_doc(doc) if doc else None


def list_enrollments_for_student(
    mongo_db: Database,
    student_id: int,
) -> List[MongoCourseEnrollment]:
    cursor = (
        mongo_db["course_enrollments"]
        .find({"student_id": int(student_id)})
        .sort("enrolled_at", DESCENDING)
    )
    return [MongoCourseEnrollment.from_doc(d) for d in cursor]


def list_enrollments_for_courses(
    mongo_db: Database,
    course_ids: Optional[Iterable[int]] = None,
    *,
    status_filter: Optional[str] = None,
    sort_asc: bool = False,
) -> List[MongoCourseEnrollment]:
    filt: Dict[str, Any] = {}
    if course_ids is not None:
        id_list = [int(c) for c in course_ids]
        if not id_list:
            return []
        filt["course_id"] = {"$in": id_list}
    if status_filter:
        filt["status"] = status_filter
    direction = ASCENDING if sort_asc else DESCENDING
    cursor = mongo_db["course_enrollments"].find(filt).sort("enrolled_at", direction)
    return [MongoCourseEnrollment.from_doc(d) for d in cursor]


def list_enrollments(
    mongo_db: Database,
    *,
    course_ids: Optional[Iterable[int]] = None,
    student_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    sort_desc: bool = False,
    limit: Optional[int] = None,
) -> List[MongoCourseEnrollment]:
    filt: Dict[str, Any] = {}
    if course_ids is not None:
        id_list = [int(c) for c in course_ids]
        if not id_list:
            return []
        filt["course_id"] = {"$in": id_list}
    if student_id is not None:
        filt["student_id"] = int(student_id)
    if status_filter:
        filt["status"] = status_filter
    direction = DESCENDING if sort_desc else ASCENDING
    cursor = mongo_db["course_enrollments"].find(filt).sort("enrolled_at", direction)
    if limit is not None:
        cursor = cursor.limit(int(limit))
    return [MongoCourseEnrollment.from_doc(d) for d in cursor]


def count_enrollments_by_course_ids(
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
        for row in mongo_db["course_enrollments"].aggregate(pipeline)
    }


def create_enrollment_doc(
    mongo_db: Database,
    *,
    student_id: int,
    course_id: int,
    enrollment_status: str = "pending",
    completion_percentage: float = 0.0,
) -> MongoCourseEnrollment:
    now = datetime.now(timezone.utc)
    enr_id = next_sequence_id(mongo_db, "course_enrollments")
    doc = {
        "id": enr_id,
        "student_id": int(student_id),
        "course_id": int(course_id),
        "enrolled_at": now,
        "completion_percentage": float(completion_percentage),
        "status": enrollment_status,
        "reviewed_at": None,
        "reviewed_by_instructor_id": None,
    }
    try:
        mongo_db["course_enrollments"].insert_one(doc)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already enrolled in this course.",
        ) from exc
    return MongoCourseEnrollment.from_doc(doc)


def claim_pending_enrollment_review(
    mongo_db: Database,
    enrollment_id: int,
    *,
    decision: str,
    reviewer_id: int,
    reviewed_at: datetime,
) -> Optional[MongoCourseEnrollment]:
    doc = mongo_db["course_enrollments"].find_one_and_update(
        {"id": int(enrollment_id), "status": "pending"},
        {
            "$set": {
                "status": decision,
                "reviewed_at": _ensure_utc(reviewed_at) or datetime.now(timezone.utc),
                "reviewed_by_instructor_id": int(reviewer_id),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    return MongoCourseEnrollment.from_doc(doc) if doc else None


def restore_enrollment_snapshot(mongo_db: Database, prev: MongoCourseEnrollment) -> None:
    mongo_db["course_enrollments"].update_one(
        {"id": prev.id},
        {
            "$set": {
                "student_id": prev.student_id,
                "course_id": prev.course_id,
                "enrolled_at": prev.enrolled_at,
                "completion_percentage": prev.completion_percentage,
                "status": prev.status,
                "reviewed_at": prev.reviewed_at,
                "reviewed_by_instructor_id": prev.reviewed_by_instructor_id,
            }
        },
        upsert=True,
    )


def update_enrollment_completion(
    mongo_db: Database,
    enrollment_id: int,
    completion_percentage: float,
) -> Optional[MongoCourseEnrollment]:
    doc = mongo_db["course_enrollments"].find_one_and_update(
        {"id": int(enrollment_id)},
        {"$set": {"completion_percentage": float(completion_percentage)}},
        return_document=ReturnDocument.AFTER,
    )
    return MongoCourseEnrollment.from_doc(doc) if doc else None


def delete_enrollment_doc(mongo_db: Database, enrollment_id: int) -> None:
    mongo_db["course_enrollments"].delete_one({"id": int(enrollment_id)})


# ---------------------------------------------------------------------------
# Transitional Phase 3B SQLite FK Shadow Sync
# Keeps SQLite foreign keys valid for non-migrated modules (quizzes,
# assignments, materials, announcements, discussions, email_deliveries, etc.)
# until subsequent Phase 3 steps complete.
# ---------------------------------------------------------------------------


def sync_course_to_sqlite_shadow(sqlite_db: Optional[Session], course: MongoCourse) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(Course).filter(Course.id == course.id).first()
        if row is None:
            row = Course(
                id=course.id,
                title=course.title,
                description=course.description,
                category=course.category,
                difficulty=course.difficulty,
                is_published=course.is_published,
                instructor_id=course.instructor_id,
                created_at=course.created_at,
                updated_at=course.updated_at,
            )
            sqlite_db.add(row)
        else:
            row.title = course.title
            row.description = course.description
            row.category = course.category
            row.difficulty = course.difficulty
            row.is_published = course.is_published
            row.instructor_id = course.instructor_id
            row.updated_at = course.updated_at
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for course_id=%s: %s", course.id, type(exc).__name__)
        raise


def delete_course_from_sqlite_shadow(sqlite_db: Optional[Session], course_id: int) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(Course).filter(Course.id == course_id).first()
        if row is not None:
            sqlite_db.delete(row)
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow delete failed for course_id=%s: %s", course_id, type(exc).__name__)
        raise


def sync_section_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    section: MongoCourseSection,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(CourseSection).filter(CourseSection.id == section.id).first()
        if row is None:
            row = CourseSection(
                id=section.id,
                course_id=section.course_id,
                title=section.title,
                description=section.description,
                order_index=section.order_index,
                created_at=section.created_at,
                updated_at=section.updated_at,
            )
            sqlite_db.add(row)
        else:
            row.course_id = section.course_id
            row.title = section.title
            row.description = section.description
            row.order_index = section.order_index
            row.updated_at = section.updated_at
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for section_id=%s: %s", section.id, type(exc).__name__)
        raise


def delete_section_from_sqlite_shadow(sqlite_db: Optional[Session], section_id: int) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(CourseSection).filter(CourseSection.id == section_id).first()
        if row is not None:
            sqlite_db.delete(row)
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow delete failed for section_id=%s: %s", section_id, type(exc).__name__)
        raise


def sync_lesson_to_sqlite_shadow(sqlite_db: Optional[Session], lesson: MongoLesson) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(Lesson).filter(Lesson.id == lesson.id).first()
        if row is None:
            row = Lesson(
                id=lesson.id,
                course_id=lesson.course_id,
                section_id=lesson.section_id,
                title=lesson.title,
                content=lesson.content,
                video_url=lesson.video_url,
                video_storage_key=lesson.video_storage_key,
                order_index=lesson.order_index,
                created_at=lesson.created_at,
                updated_at=lesson.updated_at,
            )
            sqlite_db.add(row)
        else:
            row.course_id = lesson.course_id
            row.section_id = lesson.section_id
            row.title = lesson.title
            row.content = lesson.content
            row.video_url = lesson.video_url
            row.video_storage_key = lesson.video_storage_key
            row.order_index = lesson.order_index
            row.updated_at = lesson.updated_at
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for lesson_id=%s: %s", lesson.id, type(exc).__name__)
        raise


def delete_lesson_from_sqlite_shadow(sqlite_db: Optional[Session], lesson_id: int) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if row is not None:
            sqlite_db.delete(row)
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow delete failed for lesson_id=%s: %s", lesson_id, type(exc).__name__)
        raise


def sync_lesson_progress_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    progress: MongoLessonProgress,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = (
            sqlite_db.query(LessonProgress)
            .filter(
                LessonProgress.student_id == progress.student_id,
                LessonProgress.lesson_id == progress.lesson_id,
            )
            .first()
        )
        if row is None:
            id_taken = (
                sqlite_db.query(LessonProgress.id)
                .filter(LessonProgress.id == progress.id)
                .first()
                is not None
            )
            kwargs: Dict[str, Any] = {
                "student_id": progress.student_id,
                "lesson_id": progress.lesson_id,
                "is_completed": progress.is_completed,
                "completed_at": progress.completed_at,
                "updated_at": progress.updated_at,
            }
            if not id_taken:
                kwargs["id"] = progress.id
            sqlite_db.add(LessonProgress(**kwargs))
        else:
            row.is_completed = progress.is_completed
            row.completed_at = progress.completed_at
            row.updated_at = progress.updated_at
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error(
            "SQLite shadow sync failed for lesson_progress student=%s lesson=%s: %s",
            progress.student_id,
            progress.lesson_id,
            type(exc).__name__,
        )
        raise


def sync_enrollment_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    enrollment: MongoCourseEnrollment,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = (
            sqlite_db.query(CourseEnrollment)
            .filter(CourseEnrollment.id == enrollment.id)
            .first()
        )
        if row is None:
            row = CourseEnrollment(
                id=enrollment.id,
                student_id=enrollment.student_id,
                course_id=enrollment.course_id,
                enrolled_at=enrollment.enrolled_at,
                completion_percentage=enrollment.completion_percentage,
                status=enrollment.status,
                reviewed_at=enrollment.reviewed_at,
                reviewed_by_instructor_id=enrollment.reviewed_by_instructor_id,
            )
            sqlite_db.add(row)
        else:
            row.completion_percentage = enrollment.completion_percentage
            row.status = enrollment.status
            row.reviewed_at = enrollment.reviewed_at
            row.reviewed_by_instructor_id = enrollment.reviewed_by_instructor_id
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error(
            "SQLite shadow sync failed for enrollment_id=%s: %s",
            enrollment.id,
            type(exc).__name__,
        )
        raise


def delete_enrollment_from_sqlite_shadow(
    sqlite_db: Optional[Session],
    enrollment_id: int,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = (
            sqlite_db.query(CourseEnrollment)
            .filter(CourseEnrollment.id == enrollment_id)
            .first()
        )
        if row is not None:
            sqlite_db.delete(row)
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error(
            "SQLite shadow delete failed for enrollment_id=%s: %s",
            enrollment_id,
            type(exc).__name__,
        )
        raise


def sync_sqlite_learning_content_to_mongo(
    sqlite_db: Session,
    mongo_db: Database,
) -> Dict[str, int]:
    """Sync SQLite courses, sections, lessons, lesson_progress, and enrollments into MongoDB (test seeding)."""
    counts: Dict[str, int] = {}

    courses = sqlite_db.query(Course).order_by(Course.id.asc()).all()
    max_course_id = 0
    for c in courses:
        doc = {
            "id": int(c.id),
            "title": c.title,
            "description": c.description,
            "category": c.category,
            "difficulty": c.difficulty,
            "is_published": bool(c.is_published),
            "instructor_id": int(c.instructor_id),
            "created_at": _ensure_utc(c.created_at) or datetime.now(timezone.utc),
            "updated_at": _ensure_utc(c.updated_at) or datetime.now(timezone.utc),
        }
        mongo_db["courses"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        max_course_id = max(max_course_id, doc["id"])
    sync_counter(mongo_db, "courses", max_course_id)
    counts["courses"] = len(courses)

    sections = sqlite_db.query(CourseSection).order_by(CourseSection.id.asc()).all()
    max_sec_id = 0
    for s in sections:
        doc = {
            "id": int(s.id),
            "course_id": int(s.course_id),
            "title": s.title,
            "description": s.description,
            "order_index": int(s.order_index),
            "created_at": _ensure_utc(s.created_at) or datetime.now(timezone.utc),
            "updated_at": _ensure_utc(s.updated_at) or datetime.now(timezone.utc),
        }
        mongo_db["course_sections"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        max_sec_id = max(max_sec_id, doc["id"])
    sync_counter(mongo_db, "course_sections", max_sec_id)
    counts["course_sections"] = len(sections)

    lessons = sqlite_db.query(Lesson).order_by(Lesson.id.asc()).all()
    max_lesson_id = 0
    for l in lessons:
        doc = {
            "id": int(l.id),
            "course_id": int(l.course_id),
            "section_id": int(l.section_id) if l.section_id is not None else None,
            "title": l.title,
            "content": l.content,
            "video_url": l.video_url,
            "video_storage_key": l.video_storage_key,
            "order_index": int(l.order_index),
            "created_at": _ensure_utc(l.created_at) or datetime.now(timezone.utc),
            "updated_at": _ensure_utc(l.updated_at) or datetime.now(timezone.utc),
        }
        mongo_db["lessons"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        max_lesson_id = max(max_lesson_id, doc["id"])
    sync_counter(mongo_db, "lessons", max_lesson_id)
    counts["lessons"] = len(lessons)

    progress_rows = sqlite_db.query(LessonProgress).order_by(LessonProgress.id.asc()).all()
    max_prog_id = 0
    for p in progress_rows:
        doc = {
            "id": int(p.id),
            "student_id": int(p.student_id),
            "lesson_id": int(p.lesson_id),
            "is_completed": bool(p.is_completed),
            "completed_at": _ensure_utc(p.completed_at),
            "updated_at": _ensure_utc(p.updated_at) or datetime.now(timezone.utc),
        }
        mongo_db["lesson_progress"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        max_prog_id = max(max_prog_id, doc["id"])
    sync_counter(mongo_db, "lesson_progress", max_prog_id)
    counts["lesson_progress"] = len(progress_rows)

    enrollments = sqlite_db.query(CourseEnrollment).order_by(CourseEnrollment.id.asc()).all()
    max_enr_id = 0
    for e in enrollments:
        doc = {
            "id": int(e.id),
            "student_id": int(e.student_id),
            "course_id": int(e.course_id),
            "enrolled_at": _ensure_utc(e.enrolled_at) or datetime.now(timezone.utc),
            "completion_percentage": float(e.completion_percentage),
            "status": e.status,
            "reviewed_at": _ensure_utc(e.reviewed_at),
            "reviewed_by_instructor_id": (
                int(e.reviewed_by_instructor_id)
                if e.reviewed_by_instructor_id is not None
                else None
            ),
        }
        mongo_db["course_enrollments"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        max_enr_id = max(max_enr_id, doc["id"])
    sync_counter(mongo_db, "course_enrollments", max_enr_id)
    counts["course_enrollments"] = len(enrollments)

    return counts
