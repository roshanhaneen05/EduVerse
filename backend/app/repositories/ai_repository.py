import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.ai import AIConversation, AIMessage
from app.models.ai_learning import (
    AIQuiz,
    AIQuizAnswer,
    AIQuizAttempt,
    AIQuizOption,
    AIQuizQuestion,
    StudyDeadline,
    StudyNotification,
    StudyPlan,
    StudyPreference,
    StudyTask,
)
from app.mongo_schema import next_sequence_id, sync_counter
from app.repositories.user_repository import _ensure_utc

logger = logging.getLogger(__name__)


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        return date.fromisoformat(text[:10]) if text else None
    return None


def _serialize_date(value: Any) -> Optional[str]:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed is not None else None


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MongoAIConversation:
    id: int
    user_id: int
    course_id: Optional[int]
    title: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoAIConversation":
        now = datetime.now(timezone.utc)
        cid = doc.get("course_id")
        return cls(
            id=int(doc["id"]),
            user_id=int(doc["user_id"]),
            course_id=int(cid) if cid is not None else None,
            title=str(doc["title"]),
            created_at=_ensure_utc(doc.get("created_at")) or now,
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
        )


@dataclass
class MongoAIMessage:
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoAIMessage":
        now = datetime.now(timezone.utc)
        return cls(
            id=int(doc["id"]),
            conversation_id=int(doc["conversation_id"]),
            role=str(doc["role"]),
            content=str(doc["content"]),
            created_at=_ensure_utc(doc.get("created_at")) or now,
        )


@dataclass
class MongoAIQuiz:
    id: int
    student_id: int
    course_id: int
    section_id: Optional[int]
    lesson_id: Optional[int]
    title: str
    difficulty: str
    question_type: str
    question_count: int
    created_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoAIQuiz":
        now = datetime.now(timezone.utc)
        sid = doc.get("section_id")
        lid = doc.get("lesson_id")
        return cls(
            id=int(doc["id"]),
            student_id=int(doc["student_id"]),
            course_id=int(doc["course_id"]),
            section_id=int(sid) if sid is not None else None,
            lesson_id=int(lid) if lid is not None else None,
            title=str(doc["title"]),
            difficulty=str(doc["difficulty"]),
            question_type=str(doc["question_type"]),
            question_count=int(doc["question_count"]),
            created_at=_ensure_utc(doc.get("created_at")) or now,
        )


@dataclass
class MongoAIQuizQuestion:
    id: int
    quiz_id: int
    question_text: str
    question_type: str
    correct_answer: str
    explanation: str
    difficulty: str
    points: float
    order_index: int

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoAIQuizQuestion":
        return cls(
            id=int(doc["id"]),
            quiz_id=int(doc["quiz_id"]),
            question_text=str(doc["question_text"]),
            question_type=str(doc["question_type"]),
            correct_answer=str(doc["correct_answer"]),
            explanation=str(doc["explanation"]),
            difficulty=str(doc["difficulty"]),
            points=float(doc.get("points", 1.0)),
            order_index=int(doc["order_index"]),
        )


@dataclass
class MongoAIQuizOption:
    id: int
    question_id: int
    option_text: str
    is_correct: bool
    order_index: int

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoAIQuizOption":
        return cls(
            id=int(doc["id"]),
            question_id=int(doc["question_id"]),
            option_text=str(doc["option_text"]),
            is_correct=bool(doc.get("is_correct", False)),
            order_index=int(doc.get("order_index", 1)),
        )


@dataclass
class MongoAIQuizAttempt:
    id: int
    quiz_id: int
    student_id: int
    started_at: datetime
    submitted_at: Optional[datetime]
    total_points: float
    awarded_points: float
    percentage: float
    duration_seconds: Optional[int]
    performance_level: Optional[str]
    review_requested_at: Optional[datetime]

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoAIQuizAttempt":
        now = datetime.now(timezone.utc)
        dur = doc.get("duration_seconds")
        return cls(
            id=int(doc["id"]),
            quiz_id=int(doc["quiz_id"]),
            student_id=int(doc["student_id"]),
            started_at=_ensure_utc(doc.get("started_at")) or now,
            submitted_at=_ensure_utc(doc.get("submitted_at")),
            total_points=float(doc.get("total_points", 0.0)),
            awarded_points=float(doc.get("awarded_points", 0.0)),
            percentage=float(doc.get("percentage", 0.0)),
            duration_seconds=int(dur) if dur is not None else None,
            performance_level=doc.get("performance_level"),
            review_requested_at=_ensure_utc(doc.get("review_requested_at")),
        )


@dataclass
class MongoAIQuizAnswer:
    id: int
    attempt_id: int
    question_id: int
    selected_option_id: Optional[int]
    answer_text: Optional[str]
    is_correct: bool
    awarded_points: float
    automated_feedback: Optional[str]

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoAIQuizAnswer":
        opt = doc.get("selected_option_id")
        return cls(
            id=int(doc["id"]),
            attempt_id=int(doc["attempt_id"]),
            question_id=int(doc["question_id"]),
            selected_option_id=int(opt) if opt is not None else None,
            answer_text=doc.get("answer_text"),
            is_correct=bool(doc.get("is_correct", False)),
            awarded_points=float(doc.get("awarded_points", 0.0)),
            automated_feedback=doc.get("automated_feedback"),
        )


@dataclass
class MongoStudyPreference:
    id: int
    student_id: int
    selected_course_ids: List[int]
    deadlines_json: List[Dict[str, Any]]
    available_hours_per_day: float
    preferred_time: str
    time_zone: str
    daily_duration_minutes: int
    target_completion_date: Optional[date]
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoStudyPreference":
        now = datetime.now(timezone.utc)
        return cls(
            id=int(doc["id"]),
            student_id=int(doc["student_id"]),
            selected_course_ids=[int(c) for c in (doc.get("selected_course_ids") or [])],
            deadlines_json=list(doc.get("deadlines_json") or []),
            available_hours_per_day=float(doc.get("available_hours_per_day", 2.0)),
            preferred_time=str(doc.get("preferred_time", "evening")),
            time_zone=str(doc.get("time_zone", "UTC")),
            daily_duration_minutes=int(doc.get("daily_duration_minutes", 30)),
            target_completion_date=_parse_date(doc.get("target_completion_date")),
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
        )


@dataclass
class MongoStudyPlan:
    id: int
    student_id: int
    selected_course_ids: List[int]
    target_completion_date: date
    available_hours_per_day: float
    preferred_time: str
    time_zone: str
    daily_duration_minutes: int
    recommendations_json: List[str]
    generation_mode: str
    is_active: bool
    generated_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoStudyPlan":
        now = datetime.now(timezone.utc)
        return cls(
            id=int(doc["id"]),
            student_id=int(doc["student_id"]),
            selected_course_ids=[int(c) for c in (doc.get("selected_course_ids") or [])],
            target_completion_date=_parse_date(doc.get("target_completion_date")) or now.date(),
            available_hours_per_day=float(doc.get("available_hours_per_day", 2.0)),
            preferred_time=str(doc.get("preferred_time", "evening")),
            time_zone=str(doc.get("time_zone", "UTC")),
            daily_duration_minutes=int(doc.get("daily_duration_minutes", 30)),
            recommendations_json=list(doc.get("recommendations_json") or []),
            generation_mode=str(doc.get("generation_mode", "ai")),
            is_active=bool(doc.get("is_active", True)),
            generated_at=_ensure_utc(doc.get("generated_at")) or now,
        )


@dataclass
class MongoStudyDeadline:
    id: int
    plan_id: int
    student_id: int
    course_id: int
    title: str
    deadline_type: str
    due_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoStudyDeadline":
        now = datetime.now(timezone.utc)
        return cls(
            id=int(doc["id"]),
            plan_id=int(doc["plan_id"]),
            student_id=int(doc["student_id"]),
            course_id=int(doc["course_id"]),
            title=str(doc["title"]),
            deadline_type=str(doc["deadline_type"]),
            due_at=_ensure_utc(doc.get("due_at")) or now,
        )


@dataclass
class MongoStudyTask:
    id: int
    plan_id: int
    student_id: int
    course_id: int
    section_id: Optional[int]
    lesson_id: int
    starts_at: datetime
    duration_minutes: int
    priority: str
    status: str
    rationale: str
    completed_at: Optional[datetime]
    created_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoStudyTask":
        now = datetime.now(timezone.utc)
        sid = doc.get("section_id")
        return cls(
            id=int(doc["id"]),
            plan_id=int(doc["plan_id"]),
            student_id=int(doc["student_id"]),
            course_id=int(doc["course_id"]),
            section_id=int(sid) if sid is not None else None,
            lesson_id=int(doc["lesson_id"]),
            starts_at=_ensure_utc(doc.get("starts_at")) or now,
            duration_minutes=int(doc["duration_minutes"]),
            priority=str(doc["priority"]),
            status=str(doc.get("status", "pending")),
            rationale=str(doc["rationale"]),
            completed_at=_ensure_utc(doc.get("completed_at")),
            created_at=_ensure_utc(doc.get("created_at")) or now,
        )


@dataclass
class MongoStudyNotification:
    id: int
    student_id: int
    task_id: Optional[int]
    deadline_id: Optional[int]
    notification_key: str
    notification_type: str
    message: str
    remind_at: datetime
    is_read: bool
    created_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoStudyNotification":
        now = datetime.now(timezone.utc)
        tid = doc.get("task_id")
        did = doc.get("deadline_id")
        return cls(
            id=int(doc["id"]),
            student_id=int(doc["student_id"]),
            task_id=int(tid) if tid is not None else None,
            deadline_id=int(did) if did is not None else None,
            notification_key=str(doc["notification_key"]),
            notification_type=str(doc["notification_type"]),
            message=str(doc["message"]),
            remind_at=_ensure_utc(doc.get("remind_at")) or now,
            is_read=bool(doc.get("is_read", False)),
            created_at=_ensure_utc(doc.get("created_at")) or now,
        )


# ---------------------------------------------------------------------------
# AI Conversations & Messages
# ---------------------------------------------------------------------------


def get_ai_conversation_by_id(
    mongo_db: Database,
    conversation_id: int,
) -> Optional[MongoAIConversation]:
    doc = mongo_db["ai_conversations"].find_one({"id": int(conversation_id)})
    return MongoAIConversation.from_doc(doc) if doc else None


def list_ai_conversations_for_user(
    mongo_db: Database,
    user_id: int,
) -> List[MongoAIConversation]:
    cursor = (
        mongo_db["ai_conversations"]
        .find({"user_id": int(user_id)})
        .sort("updated_at", DESCENDING)
    )
    return [MongoAIConversation.from_doc(d) for d in cursor]


def count_ai_messages_by_conversation_ids(
    mongo_db: Database,
    conversation_ids: Iterable[int],
) -> Dict[int, int]:
    ids = [int(c) for c in conversation_ids]
    if not ids:
        return {}
    pipeline = [
        {"$match": {"conversation_id": {"$in": ids}}},
        {"$group": {"_id": "$conversation_id", "count": {"$sum": 1}}},
    ]
    return {
        int(row["_id"]): int(row["count"])
        for row in mongo_db["ai_messages"].aggregate(pipeline)
    }


def list_ai_messages_for_conversation(
    mongo_db: Database,
    conversation_id: int,
) -> List[MongoAIMessage]:
    cursor = (
        mongo_db["ai_messages"]
        .find({"conversation_id": int(conversation_id)})
        .sort([("created_at", ASCENDING), ("id", ASCENDING)])
    )
    return [MongoAIMessage.from_doc(d) for d in cursor]


def create_ai_conversation_doc(
    mongo_db: Database,
    *,
    user_id: int,
    course_id: Optional[int],
    title: str,
    now: Optional[datetime] = None,
) -> MongoAIConversation:
    ts = now or datetime.now(timezone.utc)
    conv_id = next_sequence_id(mongo_db, "ai_conversations")
    doc = {
        "id": conv_id,
        "user_id": int(user_id),
        "course_id": int(course_id) if course_id is not None else None,
        "title": title,
        "created_at": ts,
        "updated_at": ts,
    }
    mongo_db["ai_conversations"].insert_one(doc)
    return MongoAIConversation.from_doc(doc)


def touch_ai_conversation_doc(
    mongo_db: Database,
    conversation_id: int,
    now: Optional[datetime] = None,
) -> Optional[MongoAIConversation]:
    ts = now or datetime.now(timezone.utc)
    doc = mongo_db["ai_conversations"].find_one_and_update(
        {"id": int(conversation_id)},
        {"$set": {"updated_at": ts}},
        return_document=ReturnDocument.AFTER,
    )
    return MongoAIConversation.from_doc(doc) if doc else None


def create_ai_message_doc(
    mongo_db: Database,
    *,
    conversation_id: int,
    role: str,
    content: str,
    now: Optional[datetime] = None,
) -> MongoAIMessage:
    ts = now or datetime.now(timezone.utc)
    msg_id = next_sequence_id(mongo_db, "ai_messages")
    doc = {
        "id": msg_id,
        "conversation_id": int(conversation_id),
        "role": role,
        "content": content,
        "created_at": ts,
    }
    mongo_db["ai_messages"].insert_one(doc)
    return MongoAIMessage.from_doc(doc)


def delete_ai_conversation_cascade_mongo(mongo_db: Database, conversation_id: int) -> None:
    cid = int(conversation_id)
    mongo_db["ai_messages"].delete_many({"conversation_id": cid})
    mongo_db["ai_conversations"].delete_one({"id": cid})


# ---------------------------------------------------------------------------
# AI Quizzes & Attempts
# ---------------------------------------------------------------------------


def create_ai_quiz_bundle_doc(
    mongo_db: Database,
    *,
    student_id: int,
    course_id: int,
    section_id: Optional[int],
    lesson_id: Optional[int],
    title: str,
    difficulty: str,
    question_type: str,
    question_count: int,
    questions_payload: List[Dict[str, Any]],
) -> Tuple[MongoAIQuiz, List[Tuple[MongoAIQuizQuestion, List[MongoAIQuizOption]]]]:
    now = datetime.now(timezone.utc)
    quiz_id = next_sequence_id(mongo_db, "ai_quizzes")
    q_doc = {
        "id": quiz_id,
        "student_id": int(student_id),
        "course_id": int(course_id),
        "section_id": int(section_id) if section_id is not None else None,
        "lesson_id": int(lesson_id) if lesson_id is not None else None,
        "title": title,
        "difficulty": difficulty,
        "question_type": question_type,
        "question_count": int(question_count),
        "created_at": now,
    }
    mongo_db["ai_quizzes"].insert_one(q_doc)

    bundles: List[Tuple[MongoAIQuizQuestion, List[MongoAIQuizOption]]] = []
    for item in questions_payload:
        quest_id = next_sequence_id(mongo_db, "ai_quiz_questions")
        quest_doc = {
            "id": quest_id,
            "quiz_id": quiz_id,
            "question_text": item["question_text"],
            "question_type": item["question_type"],
            "correct_answer": item["correct_answer"],
            "explanation": item["explanation"],
            "difficulty": item["difficulty"],
            "points": float(item.get("points", 1.0)),
            "order_index": int(item["order_index"]),
        }
        mongo_db["ai_quiz_questions"].insert_one(quest_doc)

        opts: List[MongoAIQuizOption] = []
        opt_docs = []
        for opt in item.get("options", []):
            opt_id = next_sequence_id(mongo_db, "ai_quiz_options")
            opt_doc = {
                "id": opt_id,
                "question_id": quest_id,
                "option_text": opt["option_text"],
                "is_correct": bool(opt["is_correct"]),
                "order_index": int(opt["order_index"]),
            }
            opt_docs.append(opt_doc)
            opts.append(MongoAIQuizOption.from_doc(opt_doc))
        if opt_docs:
            mongo_db["ai_quiz_options"].insert_many(opt_docs)
        bundles.append((MongoAIQuizQuestion.from_doc(quest_doc), opts))

    return MongoAIQuiz.from_doc(q_doc), bundles


def delete_ai_quiz_cascade_mongo(mongo_db: Database, quiz_id: int) -> None:
    qid = int(quiz_id)
    quest_ids = [
        int(d["id"])
        for d in mongo_db["ai_quiz_questions"].find({"quiz_id": qid}, {"_id": 0, "id": 1})
    ]
    if quest_ids:
        mongo_db["ai_quiz_options"].delete_many({"question_id": {"$in": quest_ids}})
    attempt_ids = [
        int(d["id"])
        for d in mongo_db["ai_quiz_attempts"].find({"quiz_id": qid}, {"_id": 0, "id": 1})
    ]
    if attempt_ids:
        mongo_db["ai_quiz_answers"].delete_many({"attempt_id": {"$in": attempt_ids}})
    mongo_db["ai_quiz_attempts"].delete_many({"quiz_id": qid})
    mongo_db["ai_quiz_questions"].delete_many({"quiz_id": qid})
    mongo_db["ai_quizzes"].delete_one({"id": qid})


def get_ai_quiz_by_id(mongo_db: Database, quiz_id: int) -> Optional[MongoAIQuiz]:
    doc = mongo_db["ai_quizzes"].find_one({"id": int(quiz_id)})
    return MongoAIQuiz.from_doc(doc) if doc else None


def get_ai_quizzes_by_ids(
    mongo_db: Database,
    quiz_ids: Iterable[int],
) -> Dict[int, MongoAIQuiz]:
    ids = list({int(q) for q in quiz_ids if q is not None})
    if not ids:
        return {}
    return {
        int(d["id"]): MongoAIQuiz.from_doc(d)
        for d in mongo_db["ai_quizzes"].find({"id": {"$in": ids}})
    }


def list_ai_quiz_questions_and_options(
    mongo_db: Database,
    quiz_id: int,
) -> Tuple[List[MongoAIQuizQuestion], Dict[int, List[MongoAIQuizOption]]]:
    questions = [
        MongoAIQuizQuestion.from_doc(d)
        for d in mongo_db["ai_quiz_questions"]
        .find({"quiz_id": int(quiz_id)})
        .sort("order_index", ASCENDING)
    ]
    qids = [q.id for q in questions]
    options_map: Dict[int, List[MongoAIQuizOption]] = {}
    if qids:
        cursor = (
            mongo_db["ai_quiz_options"]
            .find({"question_id": {"$in": qids}})
            .sort("order_index", ASCENDING)
        )
        for d in cursor:
            opt = MongoAIQuizOption.from_doc(d)
            options_map.setdefault(opt.question_id, []).append(opt)
    return questions, options_map


def create_ai_quiz_attempt_doc(
    mongo_db: Database,
    *,
    quiz_id: int,
    student_id: int,
    total_points: float,
) -> MongoAIQuizAttempt:
    now = datetime.now(timezone.utc)
    attempt_id = next_sequence_id(mongo_db, "ai_quiz_attempts")
    doc = {
        "id": attempt_id,
        "quiz_id": int(quiz_id),
        "student_id": int(student_id),
        "started_at": now,
        "submitted_at": None,
        "total_points": float(total_points),
        "awarded_points": 0.0,
        "percentage": 0.0,
        "duration_seconds": None,
        "performance_level": None,
        "review_requested_at": None,
    }
    mongo_db["ai_quiz_attempts"].insert_one(doc)
    return MongoAIQuizAttempt.from_doc(doc)


def get_ai_quiz_attempt_by_id(
    mongo_db: Database,
    attempt_id: int,
) -> Optional[MongoAIQuizAttempt]:
    doc = mongo_db["ai_quiz_attempts"].find_one({"id": int(attempt_id)})
    return MongoAIQuizAttempt.from_doc(doc) if doc else None


def update_ai_quiz_attempt_doc(
    mongo_db: Database,
    attempt_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoAIQuizAttempt]:
    doc = mongo_db["ai_quiz_attempts"].find_one_and_update(
        {"id": int(attempt_id)},
        {"$set": dict(updates)},
        return_document=ReturnDocument.AFTER,
    )
    return MongoAIQuizAttempt.from_doc(doc) if doc else None


def create_ai_quiz_answers_docs(
    mongo_db: Database,
    attempt_id: int,
    answers_payload: List[Dict[str, Any]],
) -> List[MongoAIQuizAnswer]:
    mongo_db["ai_quiz_answers"].delete_many({"attempt_id": int(attempt_id)})
    docs = []
    for item in answers_payload:
        ans_id = next_sequence_id(mongo_db, "ai_quiz_answers")
        sel = item.get("selected_option_id")
        docs.append(
            {
                "id": ans_id,
                "attempt_id": int(attempt_id),
                "question_id": int(item["question_id"]),
                "selected_option_id": int(sel) if sel is not None else None,
                "answer_text": item.get("answer_text"),
                "is_correct": bool(item["is_correct"]),
                "awarded_points": float(item["awarded_points"]),
                "automated_feedback": item.get("automated_feedback"),
            }
        )
    if docs:
        mongo_db["ai_quiz_answers"].insert_many(docs)
    return [MongoAIQuizAnswer.from_doc(d) for d in docs]


def list_ai_quiz_answers(
    mongo_db: Database,
    attempt_id: int,
) -> List[MongoAIQuizAnswer]:
    cursor = (
        mongo_db["ai_quiz_answers"]
        .find({"attempt_id": int(attempt_id)})
        .sort("id", ASCENDING)
    )
    return [MongoAIQuizAnswer.from_doc(d) for d in cursor]


def list_completed_ai_quiz_attempts_for_student(
    mongo_db: Database,
    student_id: int,
    limit: int = 100,
) -> List[MongoAIQuizAttempt]:
    cursor = (
        mongo_db["ai_quiz_attempts"]
        .find({"student_id": int(student_id), "submitted_at": {"$ne": None}})
        .sort("submitted_at", DESCENDING)
        .limit(limit)
    )
    return [MongoAIQuizAttempt.from_doc(d) for d in cursor]


# ---------------------------------------------------------------------------
# Study Planner
# ---------------------------------------------------------------------------


def get_study_preference(
    mongo_db: Database,
    student_id: int,
) -> Optional[MongoStudyPreference]:
    doc = mongo_db["study_preferences"].find_one({"student_id": int(student_id)})
    return MongoStudyPreference.from_doc(doc) if doc else None


def upsert_study_preference_doc(
    mongo_db: Database,
    *,
    student_id: int,
    selected_course_ids: List[int],
    deadlines_json: List[Dict[str, Any]],
    available_hours_per_day: float,
    preferred_time: str,
    time_zone: str,
    daily_duration_minutes: int,
    target_completion_date: Optional[date],
) -> MongoStudyPreference:
    now = datetime.now(timezone.utc)
    existing = get_study_preference(mongo_db, student_id)
    payload = {
        "student_id": int(student_id),
        "selected_course_ids": [int(c) for c in selected_course_ids],
        "deadlines_json": list(deadlines_json),
        "available_hours_per_day": float(available_hours_per_day),
        "preferred_time": preferred_time,
        "time_zone": time_zone,
        "daily_duration_minutes": int(daily_duration_minutes),
        "target_completion_date": _serialize_date(target_completion_date),
        "updated_at": now,
    }
    if existing:
        doc = mongo_db["study_preferences"].find_one_and_update(
            {"id": existing.id},
            {"$set": payload},
            return_document=ReturnDocument.AFTER,
        )
        assert doc is not None
        return MongoStudyPreference.from_doc(doc)

    pref_id = next_sequence_id(mongo_db, "study_preferences")
    payload["id"] = pref_id
    mongo_db["study_preferences"].insert_one(payload)
    return MongoStudyPreference.from_doc(payload)


def get_active_study_plan(
    mongo_db: Database,
    student_id: int,
) -> Optional[MongoStudyPlan]:
    doc = mongo_db["study_plans"].find_one(
        {"student_id": int(student_id), "is_active": True},
        sort=[("generated_at", DESCENDING)],
    )
    return MongoStudyPlan.from_doc(doc) if doc else None


def get_study_plan_by_id(mongo_db: Database, plan_id: int) -> Optional[MongoStudyPlan]:
    doc = mongo_db["study_plans"].find_one({"id": int(plan_id)})
    return MongoStudyPlan.from_doc(doc) if doc else None


def list_active_study_plans(
    mongo_db: Database,
    student_id: int,
) -> List[MongoStudyPlan]:
    cursor = mongo_db["study_plans"].find({"student_id": int(student_id), "is_active": True})
    return [MongoStudyPlan.from_doc(d) for d in cursor]


def deactivate_active_study_plans(mongo_db: Database, student_id: int) -> None:
    mongo_db["study_plans"].update_many(
        {"student_id": int(student_id), "is_active": True},
        {"$set": {"is_active": False}},
    )


def create_study_plan_doc(
    mongo_db: Database,
    *,
    student_id: int,
    selected_course_ids: List[int],
    target_completion_date: date,
    available_hours_per_day: float,
    preferred_time: str,
    time_zone: str,
    daily_duration_minutes: int,
    recommendations_json: List[str],
    generation_mode: str,
    generated_at: Optional[datetime] = None,
) -> MongoStudyPlan:
    now = generated_at or datetime.now(timezone.utc)
    plan_id = next_sequence_id(mongo_db, "study_plans")
    doc = {
        "id": plan_id,
        "student_id": int(student_id),
        "selected_course_ids": [int(c) for c in selected_course_ids],
        "target_completion_date": _serialize_date(target_completion_date),
        "available_hours_per_day": float(available_hours_per_day),
        "preferred_time": preferred_time,
        "time_zone": time_zone,
        "daily_duration_minutes": int(daily_duration_minutes),
        "recommendations_json": list(recommendations_json),
        "generation_mode": generation_mode,
        "is_active": True,
        "generated_at": now,
    }
    mongo_db["study_plans"].insert_one(doc)
    return MongoStudyPlan.from_doc(doc)


def create_study_deadline_doc(
    mongo_db: Database,
    *,
    plan_id: int,
    student_id: int,
    course_id: int,
    title: str,
    deadline_type: str,
    due_at: datetime,
) -> MongoStudyDeadline:
    did = next_sequence_id(mongo_db, "study_deadlines")
    doc = {
        "id": did,
        "plan_id": int(plan_id),
        "student_id": int(student_id),
        "course_id": int(course_id),
        "title": title,
        "deadline_type": deadline_type,
        "due_at": _ensure_utc(due_at) or datetime.now(timezone.utc),
    }
    mongo_db["study_deadlines"].insert_one(doc)
    return MongoStudyDeadline.from_doc(doc)


def list_study_deadlines_for_plan(
    mongo_db: Database,
    plan_id: int,
    student_id: Optional[int] = None,
) -> List[MongoStudyDeadline]:
    filt: Dict[str, Any] = {"plan_id": int(plan_id)}
    if student_id is not None:
        filt["student_id"] = int(student_id)
    cursor = mongo_db["study_deadlines"].find(filt).sort("due_at", ASCENDING)
    return [MongoStudyDeadline.from_doc(d) for d in cursor]


def list_study_deadline_ids_for_plans(
    mongo_db: Database,
    plan_ids: Iterable[int],
) -> List[int]:
    ids = [int(p) for p in plan_ids]
    if not ids:
        return []
    return [
        int(d["id"])
        for d in mongo_db["study_deadlines"].find({"plan_id": {"$in": ids}}, {"_id": 0, "id": 1})
    ]


def create_study_task_doc(
    mongo_db: Database,
    *,
    plan_id: int,
    student_id: int,
    course_id: int,
    section_id: Optional[int],
    lesson_id: int,
    starts_at: datetime,
    duration_minutes: int,
    priority: str,
    rationale: str,
) -> MongoStudyTask:
    now = datetime.now(timezone.utc)
    tid = next_sequence_id(mongo_db, "study_tasks")
    doc = {
        "id": tid,
        "plan_id": int(plan_id),
        "student_id": int(student_id),
        "course_id": int(course_id),
        "section_id": int(section_id) if section_id is not None else None,
        "lesson_id": int(lesson_id),
        "starts_at": _ensure_utc(starts_at) or now,
        "duration_minutes": int(duration_minutes),
        "priority": priority,
        "status": "pending",
        "rationale": rationale,
        "completed_at": None,
        "created_at": now,
    }
    mongo_db["study_tasks"].insert_one(doc)
    return MongoStudyTask.from_doc(doc)


def list_study_tasks_for_plan(
    mongo_db: Database,
    plan_id: int,
    *,
    student_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    exclude_task_id: Optional[int] = None,
) -> List[MongoStudyTask]:
    filt: Dict[str, Any] = {"plan_id": int(plan_id)}
    if student_id is not None:
        filt["student_id"] = int(student_id)
    if status_filter is not None:
        filt["status"] = status_filter
    if exclude_task_id is not None:
        filt["id"] = {"$ne": int(exclude_task_id)}
    cursor = mongo_db["study_tasks"].find(filt).sort("starts_at", ASCENDING)
    return [MongoStudyTask.from_doc(d) for d in cursor]


def list_study_task_ids_for_plans(
    mongo_db: Database,
    plan_ids: Iterable[int],
) -> List[int]:
    ids = [int(p) for p in plan_ids]
    if not ids:
        return []
    return [
        int(d["id"])
        for d in mongo_db["study_tasks"].find({"plan_id": {"$in": ids}}, {"_id": 0, "id": 1})
    ]


def list_prior_study_tasks(
    mongo_db: Database,
    student_id: int,
    course_ids: Iterable[int],
    limit: int = 100,
) -> List[MongoStudyTask]:
    cids = [int(c) for c in course_ids]
    if not cids:
        return []
    cursor = (
        mongo_db["study_tasks"]
        .find({"student_id": int(student_id), "course_id": {"$in": cids}})
        .sort("created_at", DESCENDING)
        .limit(limit)
    )
    return [MongoStudyTask.from_doc(d) for d in cursor]


def get_study_task_by_id(mongo_db: Database, task_id: int) -> Optional[MongoStudyTask]:
    doc = mongo_db["study_tasks"].find_one({"id": int(task_id)})
    return MongoStudyTask.from_doc(doc) if doc else None


def update_study_task_doc(
    mongo_db: Database,
    task_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoStudyTask]:
    doc = mongo_db["study_tasks"].find_one_and_update(
        {"id": int(task_id)},
        {"$set": dict(updates)},
        return_document=ReturnDocument.AFTER,
    )
    return MongoStudyTask.from_doc(doc) if doc else None


def delete_study_task_doc(mongo_db: Database, task_id: int) -> None:
    tid = int(task_id)
    mongo_db["study_notifications"].delete_many({"task_id": tid})
    mongo_db["study_tasks"].delete_one({"id": tid})


def get_study_notification_by_id(
    mongo_db: Database,
    reminder_id: int,
) -> Optional[MongoStudyNotification]:
    doc = mongo_db["study_notifications"].find_one({"id": int(reminder_id)})
    return MongoStudyNotification.from_doc(doc) if doc else None


def ensure_study_notification_doc(
    mongo_db: Database,
    *,
    student_id: int,
    key: str,
    notification_type: str,
    message: str,
    remind_at: datetime,
    task_id: Optional[int] = None,
    deadline_id: Optional[int] = None,
) -> Optional[MongoStudyNotification]:
    existing = mongo_db["study_notifications"].find_one({"notification_key": key})
    if existing is not None:
        return None
    nid = next_sequence_id(mongo_db, "study_notifications")
    now = datetime.now(timezone.utc)
    doc = {
        "id": nid,
        "student_id": int(student_id),
        "task_id": int(task_id) if task_id is not None else None,
        "deadline_id": int(deadline_id) if deadline_id is not None else None,
        "notification_key": key,
        "notification_type": notification_type,
        "message": message,
        "remind_at": _ensure_utc(remind_at) or now,
        "is_read": False,
        "created_at": now,
    }
    try:
        mongo_db["study_notifications"].insert_one(doc)
    except DuplicateKeyError:
        return None
    return MongoStudyNotification.from_doc(doc)


def list_unread_study_notifications(
    mongo_db: Database,
    student_id: int,
    remind_before: datetime,
    limit: int = 100,
) -> List[MongoStudyNotification]:
    cursor = (
        mongo_db["study_notifications"]
        .find(
            {
                "student_id": int(student_id),
                "is_read": False,
                "remind_at": {"$lte": _ensure_utc(remind_before)},
            }
        )
        .sort("remind_at", ASCENDING)
        .limit(limit)
    )
    return [MongoStudyNotification.from_doc(d) for d in cursor]


def mark_study_notifications_read(
    mongo_db: Database,
    filt: Dict[str, Any],
) -> int:
    res = mongo_db["study_notifications"].update_many(
        {**filt, "is_read": False},
        {"$set": {"is_read": True}},
    )
    return int(res.modified_count)


def update_study_notification_doc(
    mongo_db: Database,
    notification_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoStudyNotification]:
    doc = mongo_db["study_notifications"].find_one_and_update(
        {"id": int(notification_id)},
        {"$set": dict(updates)},
        return_document=ReturnDocument.AFTER,
    )
    return MongoStudyNotification.from_doc(doc) if doc else None


def find_study_notification_by_task_and_type(
    mongo_db: Database,
    task_id: int,
    student_id: int,
    notification_type: str,
) -> Optional[MongoStudyNotification]:
    doc = mongo_db["study_notifications"].find_one(
        {
            "task_id": int(task_id),
            "student_id": int(student_id),
            "notification_type": notification_type,
        }
    )
    return MongoStudyNotification.from_doc(doc) if doc else None


# ---------------------------------------------------------------------------
# Transitional SQLite Shadow Sync
# ---------------------------------------------------------------------------


def sync_ai_conversation_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    conv: MongoAIConversation,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(AIConversation).filter(AIConversation.id == conv.id).first()
        if row is None:
            sqlite_db.add(
                AIConversation(
                    id=conv.id,
                    user_id=conv.user_id,
                    course_id=conv.course_id,
                    title=conv.title,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                )
            )
        else:
            row.title = conv.title
            row.updated_at = conv.updated_at
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for ai_conversation_id=%s: %s", conv.id, type(exc).__name__)
        raise


def sync_ai_message_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    msg: MongoAIMessage,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(AIMessage).filter(AIMessage.id == msg.id).first()
        if row is None:
            sqlite_db.add(
                AIMessage(
                    id=msg.id,
                    conversation_id=msg.conversation_id,
                    role=msg.role,
                    content=msg.content,
                    created_at=msg.created_at,
                )
            )
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for ai_message_id=%s: %s", msg.id, type(exc).__name__)
        raise


def delete_ai_conversation_from_sqlite_shadow(
    sqlite_db: Optional[Session],
    conversation_id: int,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(AIConversation).filter(AIConversation.id == conversation_id).first()
        if row is not None:
            sqlite_db.delete(row)
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow delete failed for ai_conversation_id=%s: %s", conversation_id, type(exc).__name__)
        raise


def sync_ai_quiz_bundle_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    quiz: MongoAIQuiz,
    bundles: List[Tuple[MongoAIQuizQuestion, List[MongoAIQuizOption]]],
) -> None:
    if sqlite_db is None:
        return
    try:
        if sqlite_db.query(AIQuiz).filter(AIQuiz.id == quiz.id).first() is None:
            sqlite_db.add(
                AIQuiz(
                    id=quiz.id,
                    student_id=quiz.student_id,
                    course_id=quiz.course_id,
                    section_id=quiz.section_id,
                    lesson_id=quiz.lesson_id,
                    title=quiz.title,
                    difficulty=quiz.difficulty,
                    question_type=quiz.question_type,
                    question_count=quiz.question_count,
                    created_at=quiz.created_at,
                )
            )
            sqlite_db.flush()
            for q, opts in bundles:
                sqlite_db.add(
                    AIQuizQuestion(
                        id=q.id,
                        quiz_id=q.quiz_id,
                        question_text=q.question_text,
                        question_type=q.question_type,
                        correct_answer=q.correct_answer,
                        explanation=q.explanation,
                        difficulty=q.difficulty,
                        points=q.points,
                        order_index=q.order_index,
                    )
                )
                sqlite_db.flush()
                for opt in opts:
                    sqlite_db.add(
                        AIQuizOption(
                            id=opt.id,
                            question_id=opt.question_id,
                            option_text=opt.option_text,
                            is_correct=opt.is_correct,
                            order_index=opt.order_index,
                        )
                    )
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for ai_quiz_id=%s: %s", quiz.id, type(exc).__name__)
        raise


def sync_ai_quiz_attempt_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    attempt: MongoAIQuizAttempt,
    answers: Optional[List[MongoAIQuizAnswer]] = None,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(AIQuizAttempt).filter(AIQuizAttempt.id == attempt.id).first()
        if row is None:
            sqlite_db.add(
                AIQuizAttempt(
                    id=attempt.id,
                    quiz_id=attempt.quiz_id,
                    student_id=attempt.student_id,
                    started_at=attempt.started_at,
                    submitted_at=attempt.submitted_at,
                    total_points=attempt.total_points,
                    awarded_points=attempt.awarded_points,
                    percentage=attempt.percentage,
                    duration_seconds=attempt.duration_seconds,
                    performance_level=attempt.performance_level,
                    review_requested_at=attempt.review_requested_at,
                )
            )
        else:
            row.submitted_at = attempt.submitted_at
            row.total_points = attempt.total_points
            row.awarded_points = attempt.awarded_points
            row.percentage = attempt.percentage
            row.duration_seconds = attempt.duration_seconds
            row.performance_level = attempt.performance_level
            row.review_requested_at = attempt.review_requested_at
        if answers is not None:
            sqlite_db.query(AIQuizAnswer).filter(AIQuizAnswer.attempt_id == attempt.id).delete()
            for a in answers:
                sqlite_db.add(
                    AIQuizAnswer(
                        id=a.id,
                        attempt_id=a.attempt_id,
                        question_id=a.question_id,
                        selected_option_id=a.selected_option_id,
                        answer_text=a.answer_text,
                        is_correct=a.is_correct,
                        awarded_points=a.awarded_points,
                        automated_feedback=a.automated_feedback,
                    )
                )
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for ai_quiz_attempt_id=%s: %s", attempt.id, type(exc).__name__)
        raise


def sync_study_preference_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    pref: MongoStudyPreference,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(StudyPreference).filter(StudyPreference.id == pref.id).first()
        if row is None:
            sqlite_db.add(
                StudyPreference(
                    id=pref.id,
                    student_id=pref.student_id,
                    selected_course_ids=pref.selected_course_ids,
                    deadlines_json=pref.deadlines_json,
                    available_hours_per_day=pref.available_hours_per_day,
                    preferred_time=pref.preferred_time,
                    time_zone=pref.time_zone,
                    daily_duration_minutes=pref.daily_duration_minutes,
                    target_completion_date=pref.target_completion_date,
                    updated_at=pref.updated_at,
                )
            )
        else:
            row.selected_course_ids = pref.selected_course_ids
            row.deadlines_json = pref.deadlines_json
            row.available_hours_per_day = pref.available_hours_per_day
            row.preferred_time = pref.preferred_time
            row.time_zone = pref.time_zone
            row.daily_duration_minutes = pref.daily_duration_minutes
            row.target_completion_date = pref.target_completion_date
            row.updated_at = pref.updated_at
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for study_pref_id=%s: %s", pref.id, type(exc).__name__)
        raise


def sync_study_plan_bundle_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    plan: MongoStudyPlan,
    deadlines: List[MongoStudyDeadline],
    tasks: List[MongoStudyTask],
    notifications: List[MongoStudyNotification],
) -> None:
    if sqlite_db is None:
        return
    try:
        sqlite_db.query(StudyPlan).filter(
            StudyPlan.student_id == plan.student_id,
            StudyPlan.is_active.is_(True),
        ).update({StudyPlan.is_active: False}, synchronize_session=False)
        sqlite_db.add(
            StudyPlan(
                id=plan.id,
                student_id=plan.student_id,
                selected_course_ids=plan.selected_course_ids,
                target_completion_date=plan.target_completion_date,
                available_hours_per_day=plan.available_hours_per_day,
                preferred_time=plan.preferred_time,
                time_zone=plan.time_zone,
                daily_duration_minutes=plan.daily_duration_minutes,
                recommendations_json=plan.recommendations_json,
                generation_mode=plan.generation_mode,
                is_active=plan.is_active,
                generated_at=plan.generated_at,
            )
        )
        sqlite_db.flush()
        for d in deadlines:
            sqlite_db.add(
                StudyDeadline(
                    id=d.id,
                    plan_id=d.plan_id,
                    student_id=d.student_id,
                    course_id=d.course_id,
                    title=d.title,
                    deadline_type=d.deadline_type,
                    due_at=d.due_at,
                )
            )
        for t in tasks:
            sqlite_db.add(
                StudyTask(
                    id=t.id,
                    plan_id=t.plan_id,
                    student_id=t.student_id,
                    course_id=t.course_id,
                    section_id=t.section_id,
                    lesson_id=t.lesson_id,
                    starts_at=t.starts_at,
                    duration_minutes=t.duration_minutes,
                    priority=t.priority,
                    status=t.status,
                    rationale=t.rationale,
                    completed_at=t.completed_at,
                    created_at=t.created_at,
                )
            )
        sqlite_db.flush()
        for n in notifications:
            if (
                sqlite_db.query(StudyNotification.id)
                .filter(StudyNotification.notification_key == n.notification_key)
                .first()
                is None
            ):
                sqlite_db.add(
                    StudyNotification(
                        id=n.id,
                        student_id=n.student_id,
                        task_id=n.task_id,
                        deadline_id=n.deadline_id,
                        notification_key=n.notification_key,
                        notification_type=n.notification_type,
                        message=n.message,
                        remind_at=n.remind_at,
                        is_read=n.is_read,
                        created_at=n.created_at,
                    )
                )
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for study_plan_id=%s: %s", plan.id, type(exc).__name__)
        raise


def sync_study_task_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    task: MongoStudyTask,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(StudyTask).filter(StudyTask.id == task.id).first()
        if row is not None:
            row.starts_at = task.starts_at
            row.status = task.status
            row.completed_at = task.completed_at
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for study_task_id=%s: %s", task.id, type(exc).__name__)
        raise


def delete_study_task_from_sqlite_shadow(
    sqlite_db: Optional[Session],
    task_id: int,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(StudyTask).filter(StudyTask.id == task_id).first()
        if row is not None:
            sqlite_db.delete(row)
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow delete failed for study_task_id=%s: %s", task_id, type(exc).__name__)
        raise


def sync_study_notification_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    notif: MongoStudyNotification,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(StudyNotification).filter(StudyNotification.id == notif.id).first()
        if row is None:
            sqlite_db.add(
                StudyNotification(
                    id=notif.id,
                    student_id=notif.student_id,
                    task_id=notif.task_id,
                    deadline_id=notif.deadline_id,
                    notification_key=notif.notification_key,
                    notification_type=notif.notification_type,
                    message=notif.message,
                    remind_at=notif.remind_at,
                    is_read=notif.is_read,
                    created_at=notif.created_at,
                )
            )
        else:
            row.remind_at = notif.remind_at
            row.is_read = notif.is_read
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for study_notif_id=%s: %s", notif.id, type(exc).__name__)
        raise


def sync_sqlite_ai_to_mongo(sqlite_db: Session, mongo_db: Database) -> Dict[str, int]:
    """Seed helper: copy SQLite AI tutor, AI quiz, and study planner rows into MongoDB."""
    counts: Dict[str, int] = {}
    table_specs = [
        ("ai_conversations", AIConversation, lambda r: {
            "id": int(r.id), "user_id": int(r.user_id),
            "course_id": int(r.course_id) if r.course_id is not None else None,
            "title": r.title, "created_at": _ensure_utc(r.created_at), "updated_at": _ensure_utc(r.updated_at),
        }),
        ("ai_messages", AIMessage, lambda r: {
            "id": int(r.id), "conversation_id": int(r.conversation_id), "role": r.role,
            "content": r.content, "created_at": _ensure_utc(r.created_at),
        }),
        ("ai_quizzes", AIQuiz, lambda r: {
            "id": int(r.id), "student_id": int(r.student_id), "course_id": int(r.course_id),
            "section_id": int(r.section_id) if r.section_id is not None else None,
            "lesson_id": int(r.lesson_id) if r.lesson_id is not None else None,
            "title": r.title, "difficulty": r.difficulty, "question_type": r.question_type,
            "question_count": int(r.question_count), "created_at": _ensure_utc(r.created_at),
        }),
        ("ai_quiz_questions", AIQuizQuestion, lambda r: {
            "id": int(r.id), "quiz_id": int(r.quiz_id), "question_text": r.question_text,
            "question_type": r.question_type, "correct_answer": r.correct_answer,
            "explanation": r.explanation, "difficulty": r.difficulty,
            "points": float(r.points), "order_index": int(r.order_index),
        }),
        ("ai_quiz_options", AIQuizOption, lambda r: {
            "id": int(r.id), "question_id": int(r.question_id), "option_text": r.option_text,
            "is_correct": bool(r.is_correct), "order_index": int(r.order_index),
        }),
        ("ai_quiz_attempts", AIQuizAttempt, lambda r: {
            "id": int(r.id), "quiz_id": int(r.quiz_id), "student_id": int(r.student_id),
            "started_at": _ensure_utc(r.started_at), "submitted_at": _ensure_utc(r.submitted_at),
            "total_points": float(r.total_points), "awarded_points": float(r.awarded_points),
            "percentage": float(r.percentage),
            "duration_seconds": int(r.duration_seconds) if r.duration_seconds is not None else None,
            "performance_level": r.performance_level,
            "review_requested_at": _ensure_utc(r.review_requested_at),
        }),
        ("ai_quiz_answers", AIQuizAnswer, lambda r: {
            "id": int(r.id), "attempt_id": int(r.attempt_id), "question_id": int(r.question_id),
            "selected_option_id": int(r.selected_option_id) if r.selected_option_id is not None else None,
            "answer_text": r.answer_text, "is_correct": bool(r.is_correct),
            "awarded_points": float(r.awarded_points), "automated_feedback": r.automated_feedback,
        }),
        ("study_preferences", StudyPreference, lambda r: {
            "id": int(r.id), "student_id": int(r.student_id),
            "selected_course_ids": r.selected_course_ids or [],
            "deadlines_json": r.deadlines_json or [],
            "available_hours_per_day": float(r.available_hours_per_day),
            "preferred_time": r.preferred_time, "time_zone": r.time_zone,
            "daily_duration_minutes": int(r.daily_duration_minutes),
            "target_completion_date": _serialize_date(r.target_completion_date),
            "updated_at": _ensure_utc(r.updated_at),
        }),
        ("study_plans", StudyPlan, lambda r: {
            "id": int(r.id), "student_id": int(r.student_id),
            "selected_course_ids": r.selected_course_ids or [],
            "target_completion_date": _serialize_date(r.target_completion_date),
            "available_hours_per_day": float(r.available_hours_per_day),
            "preferred_time": r.preferred_time, "time_zone": r.time_zone,
            "daily_duration_minutes": int(r.daily_duration_minutes),
            "recommendations_json": r.recommendations_json or [],
            "generation_mode": r.generation_mode, "is_active": bool(r.is_active),
            "generated_at": _ensure_utc(r.generated_at),
        }),
        ("study_deadlines", StudyDeadline, lambda r: {
            "id": int(r.id), "plan_id": int(r.plan_id), "student_id": int(r.student_id),
            "course_id": int(r.course_id), "title": r.title, "deadline_type": r.deadline_type,
            "due_at": _ensure_utc(r.due_at),
        }),
        ("study_tasks", StudyTask, lambda r: {
            "id": int(r.id), "plan_id": int(r.plan_id), "student_id": int(r.student_id),
            "course_id": int(r.course_id),
            "section_id": int(r.section_id) if r.section_id is not None else None,
            "lesson_id": int(r.lesson_id), "starts_at": _ensure_utc(r.starts_at),
            "duration_minutes": int(r.duration_minutes), "priority": r.priority,
            "status": r.status, "rationale": r.rationale,
            "completed_at": _ensure_utc(r.completed_at), "created_at": _ensure_utc(r.created_at),
        }),
        ("study_notifications", StudyNotification, lambda r: {
            "id": int(r.id), "student_id": int(r.student_id),
            "task_id": int(r.task_id) if r.task_id is not None else None,
            "deadline_id": int(r.deadline_id) if r.deadline_id is not None else None,
            "notification_key": r.notification_key, "notification_type": r.notification_type,
            "message": r.message, "remind_at": _ensure_utc(r.remind_at),
            "is_read": bool(r.is_read), "created_at": _ensure_utc(r.created_at),
        }),
    ]
    for coll_name, model, builder in table_specs:
        rows = sqlite_db.query(model).order_by(model.id.asc()).all()
        max_id = 0
        for row in rows:
            doc = builder(row)
            mongo_db[coll_name].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
            max_id = max(max_id, doc["id"])
        sync_counter(mongo_db, coll_name, max_id)
        counts[coll_name] = len(rows)
    return counts
