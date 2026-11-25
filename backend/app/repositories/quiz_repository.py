import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.quiz import (
    AnswerOption,
    Question,
    Quiz,
    QuizAttempt,
    QuizAttemptAnswer,
)
from app.mongo_schema import next_sequence_id, sync_counter
from app.repositories.user_repository import _ensure_utc

logger = logging.getLogger(__name__)


def _sync_sqlite_counter(
    sqlite_db: Optional[Session],
    mongo_db: Database,
    collection_name: str,
    model: Any,
) -> None:
    if sqlite_db is None:
        return
    max_id = sqlite_db.query(func.max(model.id)).scalar()
    sync_counter(mongo_db, collection_name, int(max_id or 0))


@dataclass
class MongoQuiz:
    id: int
    course_id: int
    section_id: Optional[int]
    lesson_id: Optional[int]
    title: str
    description: Optional[str]
    passing_score: int
    is_published: bool
    time_limit_minutes: Optional[int]
    max_attempts: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoQuiz":
        now = datetime.now(timezone.utc)
        sec_id = doc.get("section_id")
        les_id = doc.get("lesson_id")
        tl = doc.get("time_limit_minutes")
        return cls(
            id=int(doc["id"]),
            course_id=int(doc["course_id"]),
            section_id=int(sec_id) if sec_id is not None else None,
            lesson_id=int(les_id) if les_id is not None else None,
            title=str(doc["title"]),
            description=doc.get("description"),
            passing_score=int(doc.get("passing_score", 70)),
            is_published=bool(doc.get("is_published", False)),
            time_limit_minutes=int(tl) if tl is not None else None,
            max_attempts=int(doc.get("max_attempts", 3)),
            created_at=_ensure_utc(doc.get("created_at")) or now,
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
        )


@dataclass
class MongoQuestion:
    id: int
    quiz_id: int
    question_text: str
    order_index: int
    points: int

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoQuestion":
        return cls(
            id=int(doc["id"]),
            quiz_id=int(doc["quiz_id"]),
            question_text=str(doc["question_text"]),
            order_index=int(doc.get("order_index", 1)),
            points=int(doc.get("points", 1)),
        )


@dataclass
class MongoAnswerOption:
    id: int
    question_id: int
    option_text: str
    is_correct: bool
    order_index: int

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoAnswerOption":
        return cls(
            id=int(doc["id"]),
            question_id=int(doc["question_id"]),
            option_text=str(doc["option_text"]),
            is_correct=bool(doc.get("is_correct", False)),
            order_index=int(doc.get("order_index", 1)),
        )


@dataclass
class MongoQuizAttempt:
    id: int
    quiz_id: Optional[int]
    student_id: Optional[int]
    score: float
    total_points: int
    passed: bool
    attempt_number: int
    is_completed: bool
    started_at: datetime
    submitted_at: datetime

    @property
    def user_id(self) -> Optional[int]:
        return self.student_id

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoQuizAttempt":
        now = datetime.now(timezone.utc)
        qid = doc.get("quiz_id")
        sid = doc.get("student_id")
        return cls(
            id=int(doc["id"]),
            quiz_id=int(qid) if qid is not None else None,
            student_id=int(sid) if sid is not None else None,
            score=float(doc.get("score", 0.0)),
            total_points=int(doc.get("total_points", 0)),
            passed=bool(doc.get("passed", False)),
            attempt_number=int(doc.get("attempt_number", 1)),
            is_completed=bool(doc.get("is_completed", True)),
            started_at=_ensure_utc(doc.get("started_at")) or now,
            submitted_at=_ensure_utc(doc.get("submitted_at")) or now,
        )


@dataclass
class MongoQuizAttemptAnswer:
    id: int
    attempt_id: int
    question_id: int
    selected_option_id: Optional[int]
    is_correct: bool
    awarded_points: int

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoQuizAttemptAnswer":
        sel = doc.get("selected_option_id")
        return cls(
            id=int(doc["id"]),
            attempt_id=int(doc["attempt_id"]),
            question_id=int(doc["question_id"]),
            selected_option_id=int(sel) if sel is not None else None,
            is_correct=bool(doc.get("is_correct", False)),
            awarded_points=int(doc.get("awarded_points", 0)),
        )


# ---------------------------------------------------------------------------
# Quizzes, Questions, Options
# ---------------------------------------------------------------------------


def get_quiz_by_id(mongo_db: Database, quiz_id: int) -> Optional[MongoQuiz]:
    doc = mongo_db["quizzes"].find_one({"id": int(quiz_id)})
    return MongoQuiz.from_doc(doc) if doc else None


def get_quizzes_by_ids(
    mongo_db: Database,
    quiz_ids: Iterable[int],
) -> Dict[int, MongoQuiz]:
    ids = list({int(q) for q in quiz_ids if q is not None})
    if not ids:
        return {}
    return {
        int(doc["id"]): MongoQuiz.from_doc(doc)
        for doc in mongo_db["quizzes"].find({"id": {"$in": ids}})
    }


def list_quizzes_for_course(
    mongo_db: Database,
    course_id: int,
    *,
    published_only: bool = False,
) -> List[MongoQuiz]:
    filt: Dict[str, Any] = {"course_id": int(course_id)}
    if published_only:
        filt["is_published"] = True
    cursor = mongo_db["quizzes"].find(filt).sort("id", ASCENDING)
    return [MongoQuiz.from_doc(d) for d in cursor]


def count_quizzes_by_course_ids(
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
        for row in mongo_db["quizzes"].aggregate(pipeline)
    }


def count_questions_by_quiz_ids(
    mongo_db: Database,
    quiz_ids: Iterable[int],
) -> Dict[int, int]:
    ids = [int(q) for q in quiz_ids]
    if not ids:
        return {}
    pipeline = [
        {"$match": {"quiz_id": {"$in": ids}}},
        {"$group": {"_id": "$quiz_id", "count": {"$sum": 1}}},
    ]
    return {
        int(row["_id"]): int(row["count"])
        for row in mongo_db["questions"].aggregate(pipeline)
    }


def list_questions_for_quiz(mongo_db: Database, quiz_id: int) -> List[MongoQuestion]:
    cursor = (
        mongo_db["questions"]
        .find({"quiz_id": int(quiz_id)})
        .sort("order_index", ASCENDING)
    )
    return [MongoQuestion.from_doc(d) for d in cursor]


def get_question_by_id(mongo_db: Database, question_id: int) -> Optional[MongoQuestion]:
    doc = mongo_db["questions"].find_one({"id": int(question_id)})
    return MongoQuestion.from_doc(doc) if doc else None


def list_options_for_question_ids(
    mongo_db: Database,
    question_ids: Iterable[int],
) -> Dict[int, List[MongoAnswerOption]]:
    ids = [int(q) for q in question_ids]
    if not ids:
        return {}
    cursor = mongo_db["answer_options"].find({"question_id": {"$in": ids}}).sort("id", ASCENDING)
    grouped: Dict[int, List[MongoAnswerOption]] = {}
    for doc in cursor:
        opt = MongoAnswerOption.from_doc(doc)
        grouped.setdefault(opt.question_id, []).append(opt)
    return grouped


def create_quiz_doc(
    mongo_db: Database,
    *,
    course_id: int,
    section_id: Optional[int],
    lesson_id: Optional[int],
    title: str,
    description: Optional[str],
    passing_score: int,
    is_published: bool,
    time_limit_minutes: Optional[int],
    max_attempts: int,
    sqlite_db: Optional[Session] = None,
) -> MongoQuiz:
    now = datetime.now(timezone.utc)
    _sync_sqlite_counter(sqlite_db, mongo_db, "quizzes", Quiz)
    quiz_id = next_sequence_id(mongo_db, "quizzes")
    doc = {
        "id": quiz_id,
        "course_id": int(course_id),
        "section_id": int(section_id) if section_id is not None else None,
        "lesson_id": int(lesson_id) if lesson_id is not None else None,
        "title": title.strip(),
        "description": description.strip() if description else None,
        "passing_score": int(passing_score),
        "is_published": bool(is_published),
        "time_limit_minutes": int(time_limit_minutes) if time_limit_minutes is not None else None,
        "max_attempts": int(max_attempts),
        "created_at": now,
        "updated_at": now,
    }
    mongo_db["quizzes"].insert_one(doc)
    return MongoQuiz.from_doc(doc)


def update_quiz_doc(
    mongo_db: Database,
    quiz_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoQuiz]:
    payload = dict(updates)
    payload["updated_at"] = datetime.now(timezone.utc)
    doc = mongo_db["quizzes"].find_one_and_update(
        {"id": int(quiz_id)},
        {"$set": payload},
        return_document=ReturnDocument.AFTER,
    )
    return MongoQuiz.from_doc(doc) if doc else None


def restore_quiz_snapshot(mongo_db: Database, prev: MongoQuiz) -> None:
    mongo_db["quizzes"].update_one(
        {"id": prev.id},
        {
            "$set": {
                "course_id": prev.course_id,
                "section_id": prev.section_id,
                "lesson_id": prev.lesson_id,
                "title": prev.title,
                "description": prev.description,
                "passing_score": prev.passing_score,
                "is_published": prev.is_published,
                "time_limit_minutes": prev.time_limit_minutes,
                "max_attempts": prev.max_attempts,
                "created_at": prev.created_at,
                "updated_at": prev.updated_at,
            }
        },
        upsert=True,
    )


def delete_quiz_cascade_mongo(mongo_db: Database, quiz_id: int) -> None:
    qid = int(quiz_id)
    question_ids = [
        int(d["id"])
        for d in mongo_db["questions"].find({"quiz_id": qid}, {"_id": 0, "id": 1})
    ]
    if question_ids:
        mongo_db["answer_options"].delete_many({"question_id": {"$in": question_ids}})
        mongo_db["quiz_attempt_answers"].delete_many({"question_id": {"$in": question_ids}})
    mongo_db["questions"].delete_many({"quiz_id": qid})
    mongo_db["quiz_attempts"].update_many({"quiz_id": qid}, {"$set": {"quiz_id": None}})
    mongo_db["quizzes"].delete_one({"id": qid})


def create_question_with_options_doc(
    mongo_db: Database,
    *,
    quiz_id: int,
    question_text: str,
    order_index: int,
    points: int,
    options_data: List[Dict[str, Any]],
    sqlite_db: Optional[Session] = None,
) -> Tuple[MongoQuestion, List[MongoAnswerOption]]:
    _sync_sqlite_counter(sqlite_db, mongo_db, "questions", Question)
    _sync_sqlite_counter(sqlite_db, mongo_db, "answer_options", AnswerOption)
    question_id = next_sequence_id(mongo_db, "questions")
    q_doc = {
        "id": question_id,
        "quiz_id": int(quiz_id),
        "question_text": question_text.strip(),
        "order_index": int(order_index),
        "points": int(points),
    }
    mongo_db["questions"].insert_one(q_doc)

    opt_docs = []
    for idx, opt in enumerate(options_data, start=1):
        opt_id = next_sequence_id(mongo_db, "answer_options")
        opt_doc = {
            "id": opt_id,
            "question_id": question_id,
            "option_text": str(opt["option_text"]).strip(),
            "is_correct": bool(opt.get("is_correct", False)),
            "order_index": int(opt.get("order_index", idx)),
        }
        opt_docs.append(opt_doc)
    if opt_docs:
        mongo_db["answer_options"].insert_many(opt_docs)

    return MongoQuestion.from_doc(q_doc), [MongoAnswerOption.from_doc(d) for d in opt_docs]


def replace_question_and_options_doc(
    mongo_db: Database,
    *,
    question_id: int,
    question_text: str,
    order_index: int,
    points: int,
    options_data: List[Dict[str, Any]],
    sqlite_db: Optional[Session] = None,
) -> Optional[Tuple[MongoQuestion, List[MongoAnswerOption]]]:
    q_doc = mongo_db["questions"].find_one_and_update(
        {"id": int(question_id)},
        {
            "$set": {
                "question_text": question_text.strip(),
                "order_index": int(order_index),
                "points": int(points),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not q_doc:
        return None

    mongo_db["answer_options"].delete_many({"question_id": int(question_id)})
    _sync_sqlite_counter(sqlite_db, mongo_db, "answer_options", AnswerOption)
    opt_docs = []
    for idx, opt in enumerate(options_data, start=1):
        opt_id = next_sequence_id(mongo_db, "answer_options")
        opt_doc = {
            "id": opt_id,
            "question_id": int(question_id),
            "option_text": str(opt["option_text"]).strip(),
            "is_correct": bool(opt.get("is_correct", False)),
            "order_index": int(opt.get("order_index", idx)),
        }
        opt_docs.append(opt_doc)
    if opt_docs:
        mongo_db["answer_options"].insert_many(opt_docs)

    return MongoQuestion.from_doc(q_doc), [MongoAnswerOption.from_doc(d) for d in opt_docs]


def restore_question_snapshot(
    mongo_db: Database,
    prev_q: MongoQuestion,
    prev_opts: List[MongoAnswerOption],
) -> None:
    mongo_db["questions"].update_one(
        {"id": prev_q.id},
        {
            "$set": {
                "quiz_id": prev_q.quiz_id,
                "question_text": prev_q.question_text,
                "order_index": prev_q.order_index,
                "points": prev_q.points,
            }
        },
        upsert=True,
    )
    mongo_db["answer_options"].delete_many({"question_id": prev_q.id})
    if prev_opts:
        mongo_db["answer_options"].insert_many(
            [
                {
                    "id": o.id,
                    "question_id": o.question_id,
                    "option_text": o.option_text,
                    "is_correct": o.is_correct,
                    "order_index": o.order_index,
                }
                for o in prev_opts
            ]
        )


def delete_question_cascade_mongo(mongo_db: Database, question_id: int) -> None:
    qid = int(question_id)
    mongo_db["answer_options"].delete_many({"question_id": qid})
    mongo_db["quiz_attempt_answers"].delete_many({"question_id": qid})
    mongo_db["questions"].delete_one({"id": qid})


# ---------------------------------------------------------------------------
# Quiz Attempts & Answers
# ---------------------------------------------------------------------------


def get_quiz_attempt_by_id(mongo_db: Database, attempt_id: int) -> Optional[MongoQuizAttempt]:
    doc = mongo_db["quiz_attempts"].find_one({"id": int(attempt_id)})
    return MongoQuizAttempt.from_doc(doc) if doc else None


def count_all_attempts_by_quiz_ids(
    mongo_db: Database,
    quiz_ids: Iterable[int],
) -> Dict[int, int]:
    ids = [int(q) for q in quiz_ids]
    if not ids:
        return {}
    pipeline = [
        {"$match": {"quiz_id": {"$in": ids}}},
        {"$group": {"_id": "$quiz_id", "count": {"$sum": 1}}},
    ]
    return {
        int(row["_id"]): int(row["count"])
        for row in mongo_db["quiz_attempts"].aggregate(pipeline)
    }


def list_completed_attempts_for_student_quiz(
    mongo_db: Database,
    quiz_id: int,
    student_id: int,
) -> List[MongoQuizAttempt]:
    cursor = mongo_db["quiz_attempts"].find(
        {
            "quiz_id": int(quiz_id),
            "student_id": int(student_id),
            "is_completed": True,
        }
    )
    return [MongoQuizAttempt.from_doc(d) for d in cursor]


def count_completed_attempts_for_student_quiz(
    mongo_db: Database,
    quiz_id: int,
    student_id: int,
) -> int:
    return int(
        mongo_db["quiz_attempts"].count_documents(
            {
                "quiz_id": int(quiz_id),
                "student_id": int(student_id),
                "is_completed": True,
            }
        )
    )


def get_latest_unfinished_attempt(
    mongo_db: Database,
    quiz_id: int,
    student_id: int,
) -> Optional[MongoQuizAttempt]:
    doc = mongo_db["quiz_attempts"].find_one(
        {
            "quiz_id": int(quiz_id),
            "student_id": int(student_id),
            "is_completed": False,
        },
        sort=[("started_at", DESCENDING)],
    )
    return MongoQuizAttempt.from_doc(doc) if doc else None


def list_completed_attempts_for_student(
    mongo_db: Database,
    student_id: int,
    *,
    quiz_id: Optional[int] = None,
) -> List[MongoQuizAttempt]:
    filt: Dict[str, Any] = {"student_id": int(student_id), "is_completed": True}
    if quiz_id is not None:
        filt["quiz_id"] = int(quiz_id)
    cursor = mongo_db["quiz_attempts"].find(filt).sort("submitted_at", DESCENDING)
    return [MongoQuizAttempt.from_doc(d) for d in cursor]


def list_quizzes_by_course_ids(
    mongo_db: Database,
    course_ids: Iterable[int],
    *,
    published_only: bool = False,
) -> List[MongoQuiz]:
    ids = [int(c) for c in course_ids]
    if not ids:
        return []
    filt: Dict[str, Any] = {"course_id": {"$in": ids}}
    if published_only:
        filt["is_published"] = True
    cursor = mongo_db["quizzes"].find(filt).sort([("course_id", ASCENDING), ("id", ASCENDING)])
    return [MongoQuiz.from_doc(d) for d in cursor]


def list_quiz_attempts(
    mongo_db: Database,
    *,
    quiz_ids: Optional[Iterable[int]] = None,
    student_id: Optional[int] = None,
    student_ids: Optional[Iterable[int]] = None,
    completed_only: bool = False,
    sort_desc: bool = False,
    limit: Optional[int] = None,
) -> List[MongoQuizAttempt]:
    filt: Dict[str, Any] = {}
    if quiz_ids is not None:
        qids = [int(q) for q in quiz_ids]
        if not qids:
            return []
        filt["quiz_id"] = {"$in": qids}
    if student_id is not None:
        filt["student_id"] = int(student_id)
    elif student_ids is not None:
        sids = [int(s) for s in student_ids]
        if not sids:
            return []
        filt["student_id"] = {"$in": sids}
    if completed_only:
        filt["is_completed"] = True
    direction = DESCENDING if sort_desc else ASCENDING
    cursor = mongo_db["quiz_attempts"].find(filt).sort("submitted_at", direction)
    if limit is not None:
        cursor = cursor.limit(int(limit))
    return [MongoQuizAttempt.from_doc(d) for d in cursor]


def count_quiz_attempts(
    mongo_db: Database,
    *,
    passed_only: Optional[bool] = None,
    completed_only: bool = False,
) -> int:
    filt: Dict[str, Any] = {}
    if passed_only is not None:
        filt["passed"] = bool(passed_only)
    if completed_only:
        filt["is_completed"] = True
    return int(mongo_db["quiz_attempts"].count_documents(filt))


def create_quiz_attempt_doc(
    mongo_db: Database,
    *,
    quiz_id: int,
    student_id: int,
    attempt_number: int,
    score: float = 0.0,
    total_points: int = 0,
    passed: bool = False,
    is_completed: bool = False,
    now: Optional[datetime] = None,
) -> MongoQuizAttempt:
    ts = now or datetime.now(timezone.utc)
    attempt_id = next_sequence_id(mongo_db, "quiz_attempts")
    doc = {
        "id": attempt_id,
        "quiz_id": int(quiz_id),
        "student_id": int(student_id),
        "score": float(score),
        "total_points": int(total_points),
        "passed": bool(passed),
        "attempt_number": int(attempt_number),
        "is_completed": bool(is_completed),
        "started_at": ts,
        "submitted_at": ts,
    }
    mongo_db["quiz_attempts"].insert_one(doc)
    return MongoQuizAttempt.from_doc(doc)


def update_quiz_attempt_doc(
    mongo_db: Database,
    attempt_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoQuizAttempt]:
    doc = mongo_db["quiz_attempts"].find_one_and_update(
        {"id": int(attempt_id)},
        {"$set": dict(updates)},
        return_document=ReturnDocument.AFTER,
    )
    return MongoQuizAttempt.from_doc(doc) if doc else None


def restore_quiz_attempt_snapshot(mongo_db: Database, prev: MongoQuizAttempt) -> None:
    mongo_db["quiz_attempts"].update_one(
        {"id": prev.id},
        {
            "$set": {
                "quiz_id": prev.quiz_id,
                "student_id": prev.student_id,
                "score": prev.score,
                "total_points": prev.total_points,
                "passed": prev.passed,
                "attempt_number": prev.attempt_number,
                "is_completed": prev.is_completed,
                "started_at": prev.started_at,
                "submitted_at": prev.submitted_at,
            }
        },
        upsert=True,
    )


def delete_quiz_attempt_doc(mongo_db: Database, attempt_id: int) -> None:
    mongo_db["quiz_attempt_answers"].delete_many({"attempt_id": int(attempt_id)})
    mongo_db["quiz_attempts"].delete_one({"id": int(attempt_id)})


def replace_attempt_answers_docs(
    mongo_db: Database,
    attempt_id: int,
    answers_data: List[Dict[str, Any]],
) -> List[MongoQuizAttemptAnswer]:
    mongo_db["quiz_attempt_answers"].delete_many({"attempt_id": int(attempt_id)})
    docs = []
    for ans in answers_data:
        ans_id = next_sequence_id(mongo_db, "quiz_attempt_answers")
        sel = ans.get("selected_option_id")
        docs.append(
            {
                "id": ans_id,
                "attempt_id": int(attempt_id),
                "question_id": int(ans["question_id"]),
                "selected_option_id": int(sel) if sel is not None else None,
                "is_correct": bool(ans.get("is_correct", False)),
                "awarded_points": int(ans.get("awarded_points", 0)),
            }
        )
    if docs:
        try:
            mongo_db["quiz_attempt_answers"].insert_many(docs)
        except DuplicateKeyError:
            mongo_db["quiz_attempt_answers"].delete_many({"attempt_id": int(attempt_id)})
            mongo_db["quiz_attempt_answers"].insert_many(docs)
    return [MongoQuizAttemptAnswer.from_doc(d) for d in docs]


def list_attempt_answers(mongo_db: Database, attempt_id: int) -> List[MongoQuizAttemptAnswer]:
    cursor = mongo_db["quiz_attempt_answers"].find({"attempt_id": int(attempt_id)})
    return [MongoQuizAttemptAnswer.from_doc(d) for d in cursor]


# ---------------------------------------------------------------------------
# Transitional SQLite Shadow Sync (preserving unmigrated Analytics/Student/AI)
# ---------------------------------------------------------------------------


def sync_quiz_to_sqlite_shadow(sqlite_db: Optional[Session], quiz: MongoQuiz) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(Quiz).filter(Quiz.id == quiz.id).first()
        if row is None:
            row = Quiz(
                id=quiz.id,
                course_id=quiz.course_id,
                section_id=quiz.section_id,
                lesson_id=quiz.lesson_id,
                title=quiz.title,
                description=quiz.description,
                passing_score=quiz.passing_score,
                is_published=quiz.is_published,
                time_limit_minutes=quiz.time_limit_minutes,
                max_attempts=quiz.max_attempts,
                created_at=quiz.created_at,
                updated_at=quiz.updated_at,
            )
            sqlite_db.add(row)
        else:
            row.course_id = quiz.course_id
            row.section_id = quiz.section_id
            row.lesson_id = quiz.lesson_id
            row.title = quiz.title
            row.description = quiz.description
            row.passing_score = quiz.passing_score
            row.is_published = quiz.is_published
            row.time_limit_minutes = quiz.time_limit_minutes
            row.max_attempts = quiz.max_attempts
            row.updated_at = quiz.updated_at
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for quiz_id=%s: %s", quiz.id, type(exc).__name__)
        raise


def delete_quiz_from_sqlite_shadow(sqlite_db: Optional[Session], quiz_id: int) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if row is not None:
            sqlite_db.delete(row)
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow delete failed for quiz_id=%s: %s", quiz_id, type(exc).__name__)
        raise


def sync_question_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    question: MongoQuestion,
    options: List[MongoAnswerOption],
) -> None:
    if sqlite_db is None:
        return
    try:
        q_row = sqlite_db.query(Question).filter(Question.id == question.id).first()
        if q_row is None:
            q_row = Question(
                id=question.id,
                quiz_id=question.quiz_id,
                question_text=question.question_text,
                order_index=question.order_index,
                points=question.points,
            )
            sqlite_db.add(q_row)
            sqlite_db.flush()
        else:
            q_row.quiz_id = question.quiz_id
            q_row.question_text = question.question_text
            q_row.order_index = question.order_index
            q_row.points = question.points

        sqlite_db.query(AnswerOption).filter(AnswerOption.question_id == question.id).delete()
        for opt in options:
            sqlite_db.add(
                AnswerOption(
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
        logger.error(
            "SQLite shadow sync failed for question_id=%s: %s",
            question.id,
            type(exc).__name__,
        )
        raise


def delete_question_from_sqlite_shadow(sqlite_db: Optional[Session], question_id: int) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(Question).filter(Question.id == question_id).first()
        if row is not None:
            sqlite_db.delete(row)
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error(
            "SQLite shadow delete failed for question_id=%s: %s",
            question_id,
            type(exc).__name__,
        )
        raise


def sync_quiz_attempt_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    attempt: MongoQuizAttempt,
    answers: Optional[List[MongoQuizAttemptAnswer]] = None,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(QuizAttempt).filter(QuizAttempt.id == attempt.id).first()
        if row is None:
            row = QuizAttempt(
                id=attempt.id,
                quiz_id=attempt.quiz_id,
                student_id=attempt.student_id,
                score=attempt.score,
                total_points=attempt.total_points,
                passed=attempt.passed,
                attempt_number=attempt.attempt_number,
                is_completed=attempt.is_completed,
                started_at=attempt.started_at,
                submitted_at=attempt.submitted_at,
            )
            sqlite_db.add(row)
        else:
            row.quiz_id = attempt.quiz_id
            row.student_id = attempt.student_id
            row.score = attempt.score
            row.total_points = attempt.total_points
            row.passed = attempt.passed
            row.attempt_number = attempt.attempt_number
            row.is_completed = attempt.is_completed
            row.started_at = attempt.started_at
            row.submitted_at = attempt.submitted_at

        if answers is not None:
            sqlite_db.query(QuizAttemptAnswer).filter(
                QuizAttemptAnswer.attempt_id == attempt.id
            ).delete()
            for ans in answers:
                sqlite_db.add(
                    QuizAttemptAnswer(
                        id=ans.id,
                        attempt_id=ans.attempt_id,
                        question_id=ans.question_id,
                        selected_option_id=ans.selected_option_id,
                        is_correct=ans.is_correct,
                        awarded_points=ans.awarded_points,
                    )
                )
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error(
            "SQLite shadow sync failed for attempt_id=%s: %s",
            attempt.id,
            type(exc).__name__,
        )
        raise


def sync_sqlite_quizzes_to_mongo(
    sqlite_db: Session,
    mongo_db: Database,
) -> Dict[str, int]:
    """Seed helper: copy SQLite quizzes, questions, options, attempts, answers to MongoDB."""
    counts: Dict[str, int] = {}

    quizzes = sqlite_db.query(Quiz).order_by(Quiz.id.asc()).all()
    max_id = 0
    for q in quizzes:
        doc = {
            "id": int(q.id),
            "course_id": int(q.course_id),
            "section_id": int(q.section_id) if q.section_id is not None else None,
            "lesson_id": int(q.lesson_id) if q.lesson_id is not None else None,
            "title": q.title,
            "description": q.description,
            "passing_score": int(q.passing_score),
            "is_published": bool(q.is_published),
            "time_limit_minutes": (
                int(q.time_limit_minutes) if q.time_limit_minutes is not None else None
            ),
            "max_attempts": int(q.max_attempts),
            "created_at": _ensure_utc(q.created_at) or datetime.now(timezone.utc),
            "updated_at": _ensure_utc(q.updated_at) or datetime.now(timezone.utc),
        }
        mongo_db["quizzes"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        max_id = max(max_id, doc["id"])
    sync_counter(mongo_db, "quizzes", max_id)
    counts["quizzes"] = len(quizzes)

    questions = sqlite_db.query(Question).order_by(Question.id.asc()).all()
    max_qid = 0
    for quest in questions:
        doc = {
            "id": int(quest.id),
            "quiz_id": int(quest.quiz_id),
            "question_text": quest.question_text,
            "order_index": int(quest.order_index),
            "points": int(quest.points),
        }
        mongo_db["questions"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        max_qid = max(max_qid, doc["id"])
    sync_counter(mongo_db, "questions", max_qid)
    counts["questions"] = len(questions)

    options = sqlite_db.query(AnswerOption).order_by(AnswerOption.id.asc()).all()
    max_oid = 0
    for opt in options:
        doc = {
            "id": int(opt.id),
            "question_id": int(opt.question_id),
            "option_text": opt.option_text,
            "is_correct": bool(opt.is_correct),
            "order_index": int(opt.order_index),
        }
        mongo_db["answer_options"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        max_oid = max(max_oid, doc["id"])
    sync_counter(mongo_db, "answer_options", max_oid)
    counts["answer_options"] = len(options)

    attempts = sqlite_db.query(QuizAttempt).order_by(QuizAttempt.id.asc()).all()
    max_aid = 0
    for att in attempts:
        doc = {
            "id": int(att.id),
            "quiz_id": int(att.quiz_id) if att.quiz_id is not None else None,
            "student_id": int(att.student_id) if att.student_id is not None else None,
            "score": float(att.score),
            "total_points": int(att.total_points),
            "passed": bool(att.passed),
            "attempt_number": int(att.attempt_number),
            "is_completed": bool(att.is_completed),
            "started_at": _ensure_utc(att.started_at) or datetime.now(timezone.utc),
            "submitted_at": _ensure_utc(att.submitted_at) or datetime.now(timezone.utc),
        }
        mongo_db["quiz_attempts"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        max_aid = max(max_aid, doc["id"])
    sync_counter(mongo_db, "quiz_attempts", max_aid)
    counts["quiz_attempts"] = len(attempts)

    answers = sqlite_db.query(QuizAttemptAnswer).order_by(QuizAttemptAnswer.id.asc()).all()
    max_ans_id = 0
    for ans in answers:
        doc = {
            "id": int(ans.id),
            "attempt_id": int(ans.attempt_id),
            "question_id": int(ans.question_id),
            "selected_option_id": (
                int(ans.selected_option_id) if ans.selected_option_id is not None else None
            ),
            "is_correct": bool(ans.is_correct),
            "awarded_points": int(ans.awarded_points),
        }
        mongo_db["quiz_attempt_answers"].update_one(
            {"id": doc["id"]}, {"$set": doc}, upsert=True
        )
        max_ans_id = max(max_ans_id, doc["id"])
    sync_counter(mongo_db, "quiz_attempt_answers", max_ans_id)
    counts["quiz_attempt_answers"] = len(answers)

    return counts
