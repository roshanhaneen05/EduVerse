import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.instructor_ai import (
    AssignmentEvaluation,
    AssignmentEvaluationCriterion,
    AssignmentRubric,
    EvaluationCriterionRubric,
    GeneratedQuestion,
    QuestionPaper,
)
from app.mongo_schema import next_sequence_id, sync_counter
from app.repositories.ai_repository import _parse_date, _serialize_date
from app.repositories.user_repository import _ensure_utc

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MongoAssignmentRubric:
    id: int
    assignment_id: int
    expected_answer: str
    updated_by_id: Optional[int]
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoAssignmentRubric":
        now = datetime.now(timezone.utc)
        uid = doc.get("updated_by_id")
        return cls(
            id=int(doc["id"]),
            assignment_id=int(doc["assignment_id"]),
            expected_answer=str(doc.get("expected_answer", "")),
            updated_by_id=int(uid) if uid is not None else None,
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
        )


@dataclass
class MongoEvaluationCriterionRubric:
    id: int
    rubric_id: int
    criterion_name: str
    maximum_marks: float
    description: str
    guidelines: str
    order_index: int

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoEvaluationCriterionRubric":
        return cls(
            id=int(doc["id"]),
            rubric_id=int(doc["rubric_id"]),
            criterion_name=str(doc["criterion_name"]),
            maximum_marks=float(doc["maximum_marks"]),
            description=str(doc["description"]),
            guidelines=str(doc.get("guidelines", "")),
            order_index=int(doc["order_index"]),
        )


@dataclass
class MongoAssignmentEvaluation:
    id: int
    submission_id: int
    assignment_id: int
    student_id: int
    instructor_id: int
    source_hash: str
    ai_suggested_marks: float
    final_marks: Optional[float]
    ai_feedback: str
    instructor_feedback: Optional[str]
    evaluation_status: str
    created_at: datetime
    approved_at: Optional[datetime]

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoAssignmentEvaluation":
        now = datetime.now(timezone.utc)
        fm = doc.get("final_marks")
        return cls(
            id=int(doc["id"]),
            submission_id=int(doc["submission_id"]),
            assignment_id=int(doc["assignment_id"]),
            student_id=int(doc["student_id"]),
            instructor_id=int(doc["instructor_id"]),
            source_hash=str(doc["source_hash"]),
            ai_suggested_marks=float(doc["ai_suggested_marks"]),
            final_marks=float(fm) if fm is not None else None,
            ai_feedback=str(doc["ai_feedback"]),
            instructor_feedback=doc.get("instructor_feedback"),
            evaluation_status=str(doc.get("evaluation_status", "pending_review")),
            created_at=_ensure_utc(doc.get("created_at")) or now,
            approved_at=_ensure_utc(doc.get("approved_at")),
        )


@dataclass
class MongoAssignmentEvaluationCriterion:
    id: int
    evaluation_id: int
    criterion_name: str
    maximum_marks: float
    suggested_marks: float
    final_marks: Optional[float]
    feedback: str
    order_index: int

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoAssignmentEvaluationCriterion":
        fm = doc.get("final_marks")
        return cls(
            id=int(doc["id"]),
            evaluation_id=int(doc["evaluation_id"]),
            criterion_name=str(doc["criterion_name"]),
            maximum_marks=float(doc["maximum_marks"]),
            suggested_marks=float(doc["suggested_marks"]),
            final_marks=float(fm) if fm is not None else None,
            feedback=str(doc["feedback"]),
            order_index=int(doc["order_index"]),
        )


@dataclass
class MongoQuestionPaper:
    id: int
    instructor_id: int
    course_id: int
    title: str
    total_marks: float
    duration_minutes: int
    difficulty: str
    section_ids_json: List[int]
    lesson_ids_json: List[int]
    exam_date: Optional[date]
    status: str
    generation_hash: Optional[str]
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime]

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoQuestionPaper":
        now = datetime.now(timezone.utc)
        return cls(
            id=int(doc["id"]),
            instructor_id=int(doc["instructor_id"]),
            course_id=int(doc["course_id"]),
            title=str(doc["title"]),
            total_marks=float(doc["total_marks"]),
            duration_minutes=int(doc["duration_minutes"]),
            difficulty=str(doc["difficulty"]),
            section_ids_json=[int(x) for x in (doc.get("section_ids_json") or [])],
            lesson_ids_json=[int(x) for x in (doc.get("lesson_ids_json") or [])],
            exam_date=_parse_date(doc.get("exam_date")),
            status=str(doc.get("status", "draft")),
            generation_hash=doc.get("generation_hash"),
            created_at=_ensure_utc(doc.get("created_at")) or now,
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
            published_at=_ensure_utc(doc.get("published_at")),
        )


@dataclass
class MongoGeneratedQuestion:
    id: int
    question_paper_id: int
    question_text: str
    question_type: str
    difficulty: str
    marks: float
    options_json: List[str]
    correct_answer: str
    explanation: str
    question_order: int

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoGeneratedQuestion":
        return cls(
            id=int(doc["id"]),
            question_paper_id=int(doc["question_paper_id"]),
            question_text=str(doc["question_text"]),
            question_type=str(doc["question_type"]),
            difficulty=str(doc["difficulty"]),
            marks=float(doc["marks"]),
            options_json=list(doc.get("options_json") or []),
            correct_answer=str(doc["correct_answer"]),
            explanation=str(doc["explanation"]),
            question_order=int(doc["question_order"]),
        )


# ---------------------------------------------------------------------------
# Rubrics
# ---------------------------------------------------------------------------


def get_rubric_by_assignment_id(
    mongo_db: Database,
    assignment_id: int,
) -> Optional[MongoAssignmentRubric]:
    doc = mongo_db["assignment_rubrics"].find_one({"assignment_id": int(assignment_id)})
    return MongoAssignmentRubric.from_doc(doc) if doc else None


def list_rubric_criteria(
    mongo_db: Database,
    rubric_id: int,
) -> List[MongoEvaluationCriterionRubric]:
    cursor = (
        mongo_db["evaluation_criterion_rubrics"]
        .find({"rubric_id": int(rubric_id)})
        .sort("order_index", ASCENDING)
    )
    return [MongoEvaluationCriterionRubric.from_doc(d) for d in cursor]


def upsert_rubric_with_criteria_doc(
    mongo_db: Database,
    *,
    assignment_id: int,
    expected_answer: str,
    updated_by_id: Optional[int],
    criteria_payload: List[Dict[str, Any]],
) -> Tuple[MongoAssignmentRubric, List[MongoEvaluationCriterionRubric]]:
    now = datetime.now(timezone.utc)
    existing = get_rubric_by_assignment_id(mongo_db, assignment_id)
    if existing is None:
        rubric_id = next_sequence_id(mongo_db, "assignment_rubrics")
        r_doc = {
            "id": rubric_id,
            "assignment_id": int(assignment_id),
            "expected_answer": expected_answer,
            "updated_by_id": int(updated_by_id) if updated_by_id is not None else None,
            "updated_at": now,
        }
        mongo_db["assignment_rubrics"].insert_one(r_doc)
    else:
        rubric_id = existing.id
        r_doc = mongo_db["assignment_rubrics"].find_one_and_update(
            {"id": rubric_id},
            {
                "$set": {
                    "expected_answer": expected_answer,
                    "updated_by_id": int(updated_by_id) if updated_by_id is not None else None,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        assert r_doc is not None

    mongo_db["evaluation_criterion_rubrics"].delete_many({"rubric_id": rubric_id})
    c_docs = []
    for index, item in enumerate(criteria_payload, start=1):
        cid = next_sequence_id(mongo_db, "evaluation_criterion_rubrics")
        c_docs.append(
            {
                "id": cid,
                "rubric_id": rubric_id,
                "criterion_name": item["criterion_name"],
                "maximum_marks": float(item["maximum_marks"]),
                "description": item["description"],
                "guidelines": item["guidelines"],
                "order_index": index,
            }
        )
    if c_docs:
        mongo_db["evaluation_criterion_rubrics"].insert_many(c_docs)
    return (
        MongoAssignmentRubric.from_doc(r_doc),
        [MongoEvaluationCriterionRubric.from_doc(d) for d in c_docs],
    )


# ---------------------------------------------------------------------------
# Assignment Evaluations
# ---------------------------------------------------------------------------


def get_evaluation_by_id(
    mongo_db: Database,
    evaluation_id: int,
) -> Optional[MongoAssignmentEvaluation]:
    doc = mongo_db["assignment_evaluations"].find_one({"id": int(evaluation_id)})
    return MongoAssignmentEvaluation.from_doc(doc) if doc else None


def list_evaluations_for_submission(
    mongo_db: Database,
    submission_id: int,
) -> List[MongoAssignmentEvaluation]:
    cursor = (
        mongo_db["assignment_evaluations"]
        .find({"submission_id": int(submission_id)})
        .sort([("created_at", DESCENDING), ("id", DESCENDING)])
    )
    return [MongoAssignmentEvaluation.from_doc(d) for d in cursor]


def list_latest_evaluations_by_submission_ids(
    mongo_db: Database,
    submission_ids: Iterable[int],
) -> Dict[int, MongoAssignmentEvaluation]:
    ids = [int(s) for s in submission_ids]
    if not ids:
        return {}
    cursor = (
        mongo_db["assignment_evaluations"]
        .find({"submission_id": {"$in": ids}})
        .sort([("created_at", DESCENDING), ("id", DESCENDING)])
    )
    latest: Dict[int, MongoAssignmentEvaluation] = {}
    for d in cursor:
        ev = MongoAssignmentEvaluation.from_doc(d)
        latest.setdefault(ev.submission_id, ev)
    return latest


def list_evaluation_criteria(
    mongo_db: Database,
    evaluation_id: int,
) -> List[MongoAssignmentEvaluationCriterion]:
    cursor = (
        mongo_db["assignment_evaluation_criteria"]
        .find({"evaluation_id": int(evaluation_id)})
        .sort("order_index", ASCENDING)
    )
    return [MongoAssignmentEvaluationCriterion.from_doc(d) for d in cursor]


def create_evaluation_with_criteria_doc(
    mongo_db: Database,
    *,
    submission_id: int,
    assignment_id: int,
    student_id: int,
    instructor_id: int,
    source_hash: str,
    ai_suggested_marks: float,
    ai_feedback: str,
    criteria_payload: List[Dict[str, Any]],
) -> Tuple[MongoAssignmentEvaluation, List[MongoAssignmentEvaluationCriterion]]:
    now = datetime.now(timezone.utc)
    ev_id = next_sequence_id(mongo_db, "assignment_evaluations")
    ev_doc = {
        "id": ev_id,
        "submission_id": int(submission_id),
        "assignment_id": int(assignment_id),
        "student_id": int(student_id),
        "instructor_id": int(instructor_id),
        "source_hash": source_hash,
        "ai_suggested_marks": float(ai_suggested_marks),
        "final_marks": None,
        "ai_feedback": ai_feedback,
        "instructor_feedback": None,
        "evaluation_status": "pending_review",
        "created_at": now,
        "approved_at": None,
    }
    mongo_db["assignment_evaluations"].insert_one(ev_doc)

    c_docs = []
    for index, item in enumerate(criteria_payload, start=1):
        cid = next_sequence_id(mongo_db, "assignment_evaluation_criteria")
        c_docs.append(
            {
                "id": cid,
                "evaluation_id": ev_id,
                "criterion_name": item["criterion_name"],
                "maximum_marks": float(item["maximum_marks"]),
                "suggested_marks": float(item["suggested_marks"]),
                "final_marks": None,
                "feedback": item["feedback"],
                "order_index": index,
            }
        )
    if c_docs:
        mongo_db["assignment_evaluation_criteria"].insert_many(c_docs)

    return (
        MongoAssignmentEvaluation.from_doc(ev_doc),
        [MongoAssignmentEvaluationCriterion.from_doc(d) for d in c_docs],
    )


def update_evaluation_doc(
    mongo_db: Database,
    evaluation_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoAssignmentEvaluation]:
    doc = mongo_db["assignment_evaluations"].find_one_and_update(
        {"id": int(evaluation_id)},
        {"$set": dict(updates)},
        return_document=ReturnDocument.AFTER,
    )
    return MongoAssignmentEvaluation.from_doc(doc) if doc else None


def update_evaluation_criterion_doc(
    mongo_db: Database,
    criterion_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoAssignmentEvaluationCriterion]:
    doc = mongo_db["assignment_evaluation_criteria"].find_one_and_update(
        {"id": int(criterion_id)},
        {"$set": dict(updates)},
        return_document=ReturnDocument.AFTER,
    )
    return MongoAssignmentEvaluationCriterion.from_doc(doc) if doc else None


# ---------------------------------------------------------------------------
# Question Papers
# ---------------------------------------------------------------------------


def get_question_paper_by_id(
    mongo_db: Database,
    paper_id: int,
) -> Optional[MongoQuestionPaper]:
    doc = mongo_db["instructor_question_papers"].find_one({"id": int(paper_id)})
    return MongoQuestionPaper.from_doc(doc) if doc else None


def get_question_paper_by_hash(
    mongo_db: Database,
    instructor_id: int,
    generation_hash: str,
) -> Optional[MongoQuestionPaper]:
    doc = mongo_db["instructor_question_papers"].find_one(
        {"instructor_id": int(instructor_id), "generation_hash": generation_hash}
    )
    return MongoQuestionPaper.from_doc(doc) if doc else None


def list_question_papers_filtered(
    mongo_db: Database,
    *,
    instructor_id: Optional[int] = None,
) -> List[MongoQuestionPaper]:
    filt: Dict[str, Any] = {}
    if instructor_id is not None:
        filt["instructor_id"] = int(instructor_id)
    cursor = mongo_db["instructor_question_papers"].find(filt).sort("updated_at", DESCENDING)
    return [MongoQuestionPaper.from_doc(d) for d in cursor]


def list_generated_questions_for_paper(
    mongo_db: Database,
    paper_id: int,
) -> List[MongoGeneratedQuestion]:
    cursor = (
        mongo_db["instructor_generated_questions"]
        .find({"question_paper_id": int(paper_id)})
        .sort("question_order", ASCENDING)
    )
    return [MongoGeneratedQuestion.from_doc(d) for d in cursor]


def create_question_paper_with_questions_doc(
    mongo_db: Database,
    *,
    instructor_id: int,
    course_id: int,
    title: str,
    total_marks: float,
    duration_minutes: int,
    difficulty: str,
    section_ids_json: List[int],
    lesson_ids_json: List[int],
    exam_date: Optional[date],
    generation_hash: Optional[str],
    questions_payload: List[Dict[str, Any]],
) -> Tuple[Optional[MongoQuestionPaper], List[MongoGeneratedQuestion]]:
    now = datetime.now(timezone.utc)
    paper_id = next_sequence_id(mongo_db, "instructor_question_papers")
    p_doc = {
        "id": paper_id,
        "instructor_id": int(instructor_id),
        "course_id": int(course_id),
        "title": title,
        "total_marks": float(total_marks),
        "duration_minutes": int(duration_minutes),
        "difficulty": difficulty,
        "section_ids_json": [int(s) for s in section_ids_json],
        "lesson_ids_json": [int(l) for l in lesson_ids_json],
        "exam_date": _serialize_date(exam_date),
        "status": "draft",
        "generation_hash": generation_hash,
        "created_at": now,
        "updated_at": now,
        "published_at": None,
    }
    try:
        mongo_db["instructor_question_papers"].insert_one(p_doc)
    except DuplicateKeyError:
        return None, []

    q_docs = []
    for item in questions_payload:
        qid = next_sequence_id(mongo_db, "instructor_generated_questions")
        q_docs.append(
            {
                "id": qid,
                "question_paper_id": paper_id,
                "question_text": item["question_text"],
                "question_type": item["question_type"],
                "difficulty": item["difficulty"],
                "marks": float(item["marks"]),
                "options_json": list(item.get("options_json") or []),
                "correct_answer": item["correct_answer"],
                "explanation": item["explanation"],
                "question_order": int(item["question_order"]),
            }
        )
    if q_docs:
        mongo_db["instructor_generated_questions"].insert_many(q_docs)

    return (
        MongoQuestionPaper.from_doc(p_doc),
        [MongoGeneratedQuestion.from_doc(d) for d in q_docs],
    )


def update_question_paper_and_replace_questions_doc(
    mongo_db: Database,
    *,
    paper_id: int,
    title: str,
    total_marks: float,
    duration_minutes: int,
    difficulty: str,
    exam_date: Optional[date],
    questions_payload: List[Dict[str, Any]],
) -> Optional[Tuple[MongoQuestionPaper, List[MongoGeneratedQuestion]]]:
    p_doc = mongo_db["instructor_question_papers"].find_one_and_update(
        {"id": int(paper_id)},
        {
            "$set": {
                "title": title,
                "total_marks": float(total_marks),
                "duration_minutes": int(duration_minutes),
                "difficulty": difficulty,
                "exam_date": _serialize_date(exam_date),
                "updated_at": datetime.now(timezone.utc),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not p_doc:
        return None

    mongo_db["instructor_generated_questions"].delete_many({"question_paper_id": int(paper_id)})
    q_docs = []
    for item in questions_payload:
        qid = next_sequence_id(mongo_db, "instructor_generated_questions")
        q_docs.append(
            {
                "id": qid,
                "question_paper_id": int(paper_id),
                "question_text": item["question_text"],
                "question_type": item["question_type"],
                "difficulty": item["difficulty"],
                "marks": float(item["marks"]),
                "options_json": list(item.get("options_json") or []),
                "correct_answer": item["correct_answer"],
                "explanation": item["explanation"],
                "question_order": int(item["question_order"]),
            }
        )
    if q_docs:
        mongo_db["instructor_generated_questions"].insert_many(q_docs)

    return (
        MongoQuestionPaper.from_doc(p_doc),
        [MongoGeneratedQuestion.from_doc(d) for d in q_docs],
    )


def update_generated_question_doc(
    mongo_db: Database,
    question_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoGeneratedQuestion]:
    doc = mongo_db["instructor_generated_questions"].find_one_and_update(
        {"id": int(question_id)},
        {"$set": dict(updates)},
        return_document=ReturnDocument.AFTER,
    )
    return MongoGeneratedQuestion.from_doc(doc) if doc else None


def update_question_paper_doc(
    mongo_db: Database,
    paper_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoQuestionPaper]:
    payload = dict(updates)
    payload.setdefault("updated_at", datetime.now(timezone.utc))
    doc = mongo_db["instructor_question_papers"].find_one_and_update(
        {"id": int(paper_id)},
        {"$set": payload},
        return_document=ReturnDocument.AFTER,
    )
    return MongoQuestionPaper.from_doc(doc) if doc else None


def delete_question_paper_cascade_mongo(mongo_db: Database, paper_id: int) -> None:
    pid = int(paper_id)
    mongo_db["instructor_generated_questions"].delete_many({"question_paper_id": pid})
    mongo_db["instructor_question_papers"].delete_one({"id": pid})


# ---------------------------------------------------------------------------
# Transitional SQLite Shadow Sync
# ---------------------------------------------------------------------------


def sync_rubric_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    rubric: MongoAssignmentRubric,
    criteria: List[MongoEvaluationCriterionRubric],
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(AssignmentRubric).filter(AssignmentRubric.id == rubric.id).first()
        if row is None:
            sqlite_db.add(
                AssignmentRubric(
                    id=rubric.id,
                    assignment_id=rubric.assignment_id,
                    expected_answer=rubric.expected_answer,
                    updated_by_id=rubric.updated_by_id,
                    updated_at=rubric.updated_at,
                )
            )
            sqlite_db.flush()
        else:
            row.expected_answer = rubric.expected_answer
            row.updated_by_id = rubric.updated_by_id
            row.updated_at = rubric.updated_at
        sqlite_db.query(EvaluationCriterionRubric).filter(
            EvaluationCriterionRubric.rubric_id == rubric.id
        ).delete()
        for c in criteria:
            sqlite_db.add(
                EvaluationCriterionRubric(
                    id=c.id,
                    rubric_id=c.rubric_id,
                    criterion_name=c.criterion_name,
                    maximum_marks=c.maximum_marks,
                    description=c.description,
                    guidelines=c.guidelines,
                    order_index=c.order_index,
                )
            )
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for rubric_id=%s: %s", rubric.id, type(exc).__name__)
        raise


def sync_evaluation_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    ev: MongoAssignmentEvaluation,
    criteria: List[MongoAssignmentEvaluationCriterion],
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(AssignmentEvaluation).filter(AssignmentEvaluation.id == ev.id).first()
        if row is None:
            sqlite_db.add(
                AssignmentEvaluation(
                    id=ev.id,
                    submission_id=ev.submission_id,
                    assignment_id=ev.assignment_id,
                    student_id=ev.student_id,
                    instructor_id=ev.instructor_id,
                    source_hash=ev.source_hash,
                    ai_suggested_marks=ev.ai_suggested_marks,
                    final_marks=ev.final_marks,
                    ai_feedback=ev.ai_feedback,
                    instructor_feedback=ev.instructor_feedback,
                    evaluation_status=ev.evaluation_status,
                    created_at=ev.created_at,
                    approved_at=ev.approved_at,
                )
            )
            sqlite_db.flush()
        else:
            row.final_marks = ev.final_marks
            row.instructor_feedback = ev.instructor_feedback
            row.evaluation_status = ev.evaluation_status
            row.approved_at = ev.approved_at
        sqlite_db.query(AssignmentEvaluationCriterion).filter(
            AssignmentEvaluationCriterion.evaluation_id == ev.id
        ).delete()
        for c in criteria:
            sqlite_db.add(
                AssignmentEvaluationCriterion(
                    id=c.id,
                    evaluation_id=c.evaluation_id,
                    criterion_name=c.criterion_name,
                    maximum_marks=c.maximum_marks,
                    suggested_marks=c.suggested_marks,
                    final_marks=c.final_marks,
                    feedback=c.feedback,
                    order_index=c.order_index,
                )
            )
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for evaluation_id=%s: %s", ev.id, type(exc).__name__)
        raise


def sync_question_paper_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    paper: MongoQuestionPaper,
    questions: List[MongoGeneratedQuestion],
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(QuestionPaper).filter(QuestionPaper.id == paper.id).first()
        if row is None:
            sqlite_db.add(
                QuestionPaper(
                    id=paper.id,
                    instructor_id=paper.instructor_id,
                    course_id=paper.course_id,
                    title=paper.title,
                    total_marks=paper.total_marks,
                    duration_minutes=paper.duration_minutes,
                    difficulty=paper.difficulty,
                    section_ids_json=paper.section_ids_json,
                    lesson_ids_json=paper.lesson_ids_json,
                    exam_date=paper.exam_date,
                    status=paper.status,
                    generation_hash=paper.generation_hash,
                    created_at=paper.created_at,
                    updated_at=paper.updated_at,
                    published_at=paper.published_at,
                )
            )
            sqlite_db.flush()
        else:
            row.title = paper.title
            row.total_marks = paper.total_marks
            row.duration_minutes = paper.duration_minutes
            row.difficulty = paper.difficulty
            row.exam_date = paper.exam_date
            row.status = paper.status
            row.updated_at = paper.updated_at
            row.published_at = paper.published_at
        sqlite_db.query(GeneratedQuestion).filter(
            GeneratedQuestion.question_paper_id == paper.id
        ).delete()
        for q in questions:
            sqlite_db.add(
                GeneratedQuestion(
                    id=q.id,
                    question_paper_id=q.question_paper_id,
                    question_text=q.question_text,
                    question_type=q.question_type,
                    difficulty=q.difficulty,
                    marks=q.marks,
                    options_json=q.options_json,
                    correct_answer=q.correct_answer,
                    explanation=q.explanation,
                    question_order=q.question_order,
                )
            )
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for question_paper_id=%s: %s", paper.id, type(exc).__name__)
        raise


def delete_question_paper_from_sqlite_shadow(
    sqlite_db: Optional[Session],
    paper_id: int,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
        if row is not None:
            sqlite_db.delete(row)
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow delete failed for question_paper_id=%s: %s", paper_id, type(exc).__name__)
        raise


def sync_sqlite_instructor_ai_to_mongo(
    sqlite_db: Session,
    mongo_db: Database,
) -> Dict[str, int]:
    """Seed helper: copy SQLite instructor AI tables into MongoDB."""
    counts: Dict[str, int] = {}
    table_specs = [
        ("assignment_rubrics", AssignmentRubric, lambda r: {
            "id": int(r.id), "assignment_id": int(r.assignment_id),
            "expected_answer": r.expected_answer,
            "updated_by_id": int(r.updated_by_id) if r.updated_by_id is not None else None,
            "updated_at": _ensure_utc(r.updated_at),
        }),
        ("evaluation_criterion_rubrics", EvaluationCriterionRubric, lambda r: {
            "id": int(r.id), "rubric_id": int(r.rubric_id),
            "criterion_name": r.criterion_name, "maximum_marks": float(r.maximum_marks),
            "description": r.description, "guidelines": r.guidelines, "order_index": int(r.order_index),
        }),
        ("assignment_evaluations", AssignmentEvaluation, lambda r: {
            "id": int(r.id), "submission_id": int(r.submission_id), "assignment_id": int(r.assignment_id),
            "student_id": int(r.student_id), "instructor_id": int(r.instructor_id),
            "source_hash": r.source_hash, "ai_suggested_marks": float(r.ai_suggested_marks),
            "final_marks": float(r.final_marks) if r.final_marks is not None else None,
            "ai_feedback": r.ai_feedback, "instructor_feedback": r.instructor_feedback,
            "evaluation_status": r.evaluation_status,
            "created_at": _ensure_utc(r.created_at), "approved_at": _ensure_utc(r.approved_at),
        }),
        ("assignment_evaluation_criteria", AssignmentEvaluationCriterion, lambda r: {
            "id": int(r.id), "evaluation_id": int(r.evaluation_id),
            "criterion_name": r.criterion_name, "maximum_marks": float(r.maximum_marks),
            "suggested_marks": float(r.suggested_marks),
            "final_marks": float(r.final_marks) if r.final_marks is not None else None,
            "feedback": r.feedback, "order_index": int(r.order_index),
        }),
        ("instructor_question_papers", QuestionPaper, lambda r: {
            "id": int(r.id), "instructor_id": int(r.instructor_id), "course_id": int(r.course_id),
            "title": r.title, "total_marks": float(r.total_marks),
            "duration_minutes": int(r.duration_minutes), "difficulty": r.difficulty,
            "section_ids_json": r.section_ids_json or [], "lesson_ids_json": r.lesson_ids_json or [],
            "exam_date": _serialize_date(r.exam_date), "status": r.status,
            "generation_hash": r.generation_hash,
            "created_at": _ensure_utc(r.created_at), "updated_at": _ensure_utc(r.updated_at),
            "published_at": _ensure_utc(r.published_at),
        }),
        ("instructor_generated_questions", GeneratedQuestion, lambda r: {
            "id": int(r.id), "question_paper_id": int(r.question_paper_id),
            "question_text": r.question_text, "question_type": r.question_type,
            "difficulty": r.difficulty, "marks": float(r.marks),
            "options_json": r.options_json or [], "correct_answer": r.correct_answer,
            "explanation": r.explanation, "question_order": int(r.question_order),
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
