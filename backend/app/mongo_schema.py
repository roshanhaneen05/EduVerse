import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pymongo import ASCENDING, IndexModel, ReturnDocument
from pymongo.database import Database
from pymongo.errors import CollectionInvalid, OperationFailure

logger = logging.getLogger(__name__)

COUNTERS_COLLECTION = "counters"


@dataclass(frozen=True)
class IndexSpec:
    keys: Tuple[Tuple[str, int], ...]
    name: str
    unique: bool = False
    partial_filter: Optional[Dict[str, Any]] = None

    def to_index_model(self) -> IndexModel:
        kwargs: Dict[str, Any] = {"name": self.name, "unique": self.unique}
        if self.partial_filter is not None:
            kwargs["partialFilterExpression"] = self.partial_filter
        return IndexModel(list(self.keys), **kwargs)


# Topologically ordered collections (parents before children)
COLLECTION_NAMES: Tuple[str, ...] = (
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
    "assignment_rubrics",
    "evaluation_criterion_rubrics",
    "assignment_evaluations",
    "assignment_evaluation_criteria",
    "instructor_question_papers",
    "instructor_generated_questions",
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
)


def _id_index(collection_name: str) -> IndexSpec:
    return IndexSpec(
        keys=(("id", ASCENDING),),
        name=f"uq_{collection_name}_id",
        unique=True,
    )


COLLECTION_INDEXES: Dict[str, Tuple[IndexSpec, ...]] = {
    "users": (
        _id_index("users"),
        IndexSpec((("email", ASCENDING),), name="uq_users_email", unique=True),
        IndexSpec((("role", ASCENDING),), name="ix_users_role"),
    ),
    "instructor_profiles": (
        _id_index("instructor_profiles"),
        IndexSpec((("user_id", ASCENDING),), name="uq_instructor_profiles_user_id", unique=True),
        IndexSpec(
            (("instructor_id", ASCENDING),),
            name="uq_instructor_profiles_instructor_id",
            unique=True,
        ),
    ),
    "instructor_password_tokens": (
        _id_index("instructor_password_tokens"),
        IndexSpec((("token_hash", ASCENDING),), name="uq_instructor_password_tokens_hash", unique=True),
        IndexSpec((("user_id", ASCENDING),), name="ix_instructor_password_tokens_user_id"),
    ),
    "courses": (
        _id_index("courses"),
        IndexSpec((("instructor_id", ASCENDING),), name="ix_courses_instructor_id"),
        IndexSpec((("category", ASCENDING),), name="ix_courses_category"),
        IndexSpec((("is_published", ASCENDING),), name="ix_courses_is_published"),
    ),
    "course_sections": (
        _id_index("course_sections"),
        IndexSpec(
            (("course_id", ASCENDING), ("order_index", ASCENDING)),
            name="ix_course_sections_course_order",
        ),
    ),
    "lessons": (
        _id_index("lessons"),
        IndexSpec(
            (("course_id", ASCENDING), ("order_index", ASCENDING)),
            name="ix_lessons_course_order",
        ),
        IndexSpec((("section_id", ASCENDING),), name="ix_lessons_section_id"),
    ),
    "lesson_progress": (
        _id_index("lesson_progress"),
        IndexSpec(
            (("student_id", ASCENDING), ("lesson_id", ASCENDING)),
            name="uq_student_lesson_progress",
            unique=True,
        ),
        IndexSpec((("lesson_id", ASCENDING),), name="ix_lesson_progress_lesson_id"),
    ),
    "course_enrollments": (
        _id_index("course_enrollments"),
        IndexSpec(
            (("student_id", ASCENDING), ("course_id", ASCENDING)),
            name="uq_student_course_enrollment",
            unique=True,
        ),
        IndexSpec((("course_id", ASCENDING),), name="ix_course_enrollments_course_id"),
        IndexSpec((("status", ASCENDING),), name="ix_course_enrollments_status"),
    ),
    "email_deliveries": (
        _id_index("email_deliveries"),
        IndexSpec(
            (("enrollment_id", ASCENDING), ("event_type", ASCENDING)),
            name="uq_email_delivery_enrollment_event",
            unique=True,
        ),
        IndexSpec((("status", ASCENDING),), name="ix_email_deliveries_status"),
    ),
    "quizzes": (
        _id_index("quizzes"),
        IndexSpec((("course_id", ASCENDING),), name="ix_quizzes_course_id"),
        IndexSpec((("section_id", ASCENDING),), name="ix_quizzes_section_id"),
        IndexSpec((("lesson_id", ASCENDING),), name="ix_quizzes_lesson_id"),
    ),
    "questions": (
        _id_index("questions"),
        IndexSpec(
            (("quiz_id", ASCENDING), ("order_index", ASCENDING)),
            name="ix_questions_quiz_order",
        ),
    ),
    "answer_options": (
        _id_index("answer_options"),
        IndexSpec((("question_id", ASCENDING),), name="ix_answer_options_question_id"),
    ),
    "quiz_attempts": (
        _id_index("quiz_attempts"),
        IndexSpec((("quiz_id", ASCENDING),), name="ix_quiz_attempts_quiz_id"),
        IndexSpec((("student_id", ASCENDING),), name="ix_quiz_attempts_student_id"),
    ),
    "quiz_attempt_answers": (
        _id_index("quiz_attempt_answers"),
        IndexSpec(
            (("attempt_id", ASCENDING), ("question_id", ASCENDING)),
            name="uq_attempt_question",
            unique=True,
        ),
        IndexSpec((("question_id", ASCENDING),), name="ix_quiz_attempt_answers_question_id"),
    ),
    "assignments": (
        _id_index("assignments"),
        IndexSpec((("course_id", ASCENDING),), name="ix_assignments_course_id"),
        IndexSpec((("section_id", ASCENDING),), name="ix_assignments_section_id"),
    ),
    "assignment_submissions": (
        _id_index("assignment_submissions"),
        IndexSpec(
            (("assignment_id", ASCENDING), ("student_id", ASCENDING)),
            name="uq_assignment_student_submission",
            unique=True,
        ),
        IndexSpec((("student_id", ASCENDING),), name="ix_assignment_submissions_student_id"),
        IndexSpec((("graded_by_id", ASCENDING),), name="ix_assignment_submissions_graded_by_id"),
    ),
    "assignment_rubrics": (
        _id_index("assignment_rubrics"),
        IndexSpec(
            (("assignment_id", ASCENDING),),
            name="uq_assignment_rubrics_assignment_id",
            unique=True,
        ),
    ),
    "evaluation_criterion_rubrics": (
        _id_index("evaluation_criterion_rubrics"),
        IndexSpec(
            (("rubric_id", ASCENDING), ("order_index", ASCENDING)),
            name="uq_rubric_criterion_order",
            unique=True,
        ),
    ),
    "assignment_evaluations": (
        _id_index("assignment_evaluations"),
        IndexSpec((("submission_id", ASCENDING),), name="ix_assignment_evaluations_submission_id"),
        IndexSpec((("assignment_id", ASCENDING),), name="ix_assignment_evaluations_assignment_id"),
        IndexSpec((("student_id", ASCENDING),), name="ix_assignment_evaluations_student_id"),
        IndexSpec((("instructor_id", ASCENDING),), name="ix_assignment_evaluations_instructor_id"),
    ),
    "assignment_evaluation_criteria": (
        _id_index("assignment_evaluation_criteria"),
        IndexSpec(
            (("evaluation_id", ASCENDING), ("order_index", ASCENDING)),
            name="uq_eval_criterion_order",
            unique=True,
        ),
    ),
    "instructor_question_papers": (
        _id_index("instructor_question_papers"),
        IndexSpec(
            (("instructor_id", ASCENDING), ("generation_hash", ASCENDING)),
            name="uq_question_paper_generation_hash",
            unique=True,
            partial_filter={"generation_hash": {"$type": "string"}},
        ),
        IndexSpec((("course_id", ASCENDING),), name="ix_question_papers_course_id"),
    ),
    "instructor_generated_questions": (
        _id_index("instructor_generated_questions"),
        IndexSpec(
            (("question_paper_id", ASCENDING), ("question_order", ASCENDING)),
            name="uq_generated_question_order",
            unique=True,
        ),
    ),
    "learning_materials": (
        _id_index("learning_materials"),
        IndexSpec((("storage_key", ASCENDING),), name="uq_learning_materials_storage_key", unique=True),
        IndexSpec((("course_id", ASCENDING),), name="ix_learning_materials_course_id"),
        IndexSpec((("uploader_id", ASCENDING),), name="ix_learning_materials_uploader_id"),
        IndexSpec((("section_id", ASCENDING),), name="ix_learning_materials_section_id"),
        IndexSpec((("lesson_id", ASCENDING),), name="ix_learning_materials_lesson_id"),
    ),
    "course_announcements": (
        _id_index("course_announcements"),
        IndexSpec(
            (("course_id", ASCENDING), ("is_published", ASCENDING)),
            name="ix_course_announcements_course_published",
        ),
        IndexSpec((("instructor_id", ASCENDING),), name="ix_course_announcements_instructor_id"),
    ),
    "course_discussions": (
        _id_index("course_discussions"),
        IndexSpec((("course_id", ASCENDING),), name="ix_course_discussions_course_id"),
        IndexSpec((("user_id", ASCENDING),), name="ix_course_discussions_user_id"),
    ),
    "discussion_replies": (
        _id_index("discussion_replies"),
        IndexSpec((("thread_id", ASCENDING),), name="ix_discussion_replies_thread_id"),
        IndexSpec((("user_id", ASCENDING),), name="ix_discussion_replies_user_id"),
        IndexSpec((("parent_reply_id", ASCENDING),), name="ix_discussion_replies_parent_reply_id"),
    ),
    "notifications": (
        _id_index("notifications"),
        IndexSpec(
            (("user_id", ASCENDING), ("is_read", ASCENDING)),
            name="ix_notifications_user_read",
        ),
        IndexSpec((("notification_type", ASCENDING),), name="ix_notifications_type"),
    ),
    "ai_conversations": (
        _id_index("ai_conversations"),
        IndexSpec((("user_id", ASCENDING),), name="ix_ai_conversations_user_id"),
        IndexSpec((("course_id", ASCENDING),), name="ix_ai_conversations_course_id"),
    ),
    "ai_messages": (
        _id_index("ai_messages"),
        IndexSpec(
            (("conversation_id", ASCENDING), ("created_at", ASCENDING)),
            name="ix_ai_messages_conv_created",
        ),
    ),
    "ai_quizzes": (
        _id_index("ai_quizzes"),
        IndexSpec((("student_id", ASCENDING),), name="ix_ai_quizzes_student_id"),
        IndexSpec((("course_id", ASCENDING),), name="ix_ai_quizzes_course_id"),
        IndexSpec((("section_id", ASCENDING),), name="ix_ai_quizzes_section_id"),
        IndexSpec((("lesson_id", ASCENDING),), name="ix_ai_quizzes_lesson_id"),
    ),
    "ai_quiz_questions": (
        _id_index("ai_quiz_questions"),
        IndexSpec(
            (("quiz_id", ASCENDING), ("order_index", ASCENDING)),
            name="uq_ai_quiz_question_order",
            unique=True,
        ),
    ),
    "ai_quiz_options": (
        _id_index("ai_quiz_options"),
        IndexSpec((("question_id", ASCENDING),), name="ix_ai_quiz_options_question_id"),
    ),
    "ai_quiz_attempts": (
        _id_index("ai_quiz_attempts"),
        IndexSpec((("quiz_id", ASCENDING),), name="ix_ai_quiz_attempts_quiz_id"),
        IndexSpec((("student_id", ASCENDING),), name="ix_ai_quiz_attempts_student_id"),
    ),
    "ai_quiz_answers": (
        _id_index("ai_quiz_answers"),
        IndexSpec(
            (("attempt_id", ASCENDING), ("question_id", ASCENDING)),
            name="uq_ai_quiz_attempt_question",
            unique=True,
        ),
        IndexSpec((("question_id", ASCENDING),), name="ix_ai_quiz_answers_question_id"),
    ),
    "study_preferences": (
        _id_index("study_preferences"),
        IndexSpec((("student_id", ASCENDING),), name="uq_study_preferences_student_id", unique=True),
    ),
    "study_plans": (
        _id_index("study_plans"),
        IndexSpec(
            (("student_id", ASCENDING), ("is_active", ASCENDING)),
            name="ix_study_plans_student_active",
        ),
    ),
    "study_deadlines": (
        _id_index("study_deadlines"),
        IndexSpec((("plan_id", ASCENDING),), name="ix_study_deadlines_plan_id"),
        IndexSpec((("student_id", ASCENDING),), name="ix_study_deadlines_student_id"),
        IndexSpec((("course_id", ASCENDING),), name="ix_study_deadlines_course_id"),
    ),
    "study_tasks": (
        _id_index("study_tasks"),
        IndexSpec(
            (("plan_id", ASCENDING), ("lesson_id", ASCENDING)),
            name="uq_study_plan_lesson",
            unique=True,
        ),
        IndexSpec((("student_id", ASCENDING),), name="ix_study_tasks_student_id"),
        IndexSpec((("course_id", ASCENDING),), name="ix_study_tasks_course_id"),
        IndexSpec((("lesson_id", ASCENDING),), name="ix_study_tasks_lesson_id"),
        IndexSpec((("starts_at", ASCENDING),), name="ix_study_tasks_starts_at"),
        IndexSpec((("status", ASCENDING),), name="ix_study_tasks_status"),
    ),
    "study_notifications": (
        _id_index("study_notifications"),
        IndexSpec(
            (("notification_key", ASCENDING),),
            name="uq_study_notifications_key",
            unique=True,
        ),
        IndexSpec((("student_id", ASCENDING),), name="ix_study_notifications_student_id"),
        IndexSpec((("task_id", ASCENDING),), name="ix_study_notifications_task_id"),
        IndexSpec((("deadline_id", ASCENDING),), name="ix_study_notifications_deadline_id"),
        IndexSpec((("remind_at", ASCENDING),), name="ix_study_notifications_remind_at"),
        IndexSpec((("is_read", ASCENDING),), name="ix_study_notifications_is_read"),
    ),
}


def check_unique_index_conflicts(db: Database, collection_name: str) -> List[str]:
    """
    Inspect existing documents in a collection for duplicates that would violate
    planned unique indexes before attempting index creation.
    """
    conflicts: List[str] = []
    if db[collection_name].estimated_document_count() == 0:
        return conflicts

    specs = COLLECTION_INDEXES.get(collection_name, ())
    for spec in specs:
        if not spec.unique:
            continue
        fields = [k for k, _ in spec.keys]
        match_stage: Dict[str, Any] = (
            dict(spec.partial_filter)
            if spec.partial_filter is not None
            else {f: {"$exists": True} for f in fields}
        )
        group_id = {f: f"${f}" for f in fields}
        pipeline = [
            {"$match": match_stage},
            {"$group": {"_id": group_id, "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
            {"$limit": 5},
        ]
        dups = list(db[collection_name].aggregate(pipeline))
        if dups:
            conflicts.append(
                f"{collection_name}.{spec.name} has {len(dups)}+ duplicate key group(s) on {fields}"
            )
    return conflicts


def sync_counter(db: Database, collection_name: str, min_seq: int) -> int:
    """
    Ensure the sequence counter for `collection_name` is at least `min_seq`
    without ever decreasing an existing counter value.
    """
    doc = db[COUNTERS_COLLECTION].find_one_and_update(
        {"_id": collection_name},
        {"$max": {"seq": int(min_seq)}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(doc["seq"])


def next_sequence_id(db: Database, collection_name: str) -> int:
    """
    Atomically allocate and return the next sequential integer ID for a collection.
    If the counter document did not exist yet, initialize from existing max(id) first
    so allocated IDs never collide with migrated records.
    """
    if db[COUNTERS_COLLECTION].find_one({"_id": collection_name}, {"_id": 1}) is None:
        max_doc = db[collection_name].find_one(
            {"id": {"$type": "number"}},
            sort=[("id", -1)],
            projection={"id": 1},
        )
        max_id = int(max_doc["id"]) if max_doc and "id" in max_doc else 0
        sync_counter(db, collection_name, max_id)

    doc = db[COUNTERS_COLLECTION].find_one_and_update(
        {"_id": collection_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(doc["seq"])


def ensure_mongo_collections_and_indexes(
    db: Database,
    *,
    initialize_counters: bool = True,
) -> Dict[str, Any]:
    """
    Idempotently create all EduVerse collections, indexes, and sequence counters
    without dropping or overwriting existing collections or unrelated documents.
    """
    existing = set(db.list_collection_names())
    created_collections: List[str] = []
    existing_collections: List[str] = []
    index_summary: Dict[str, int] = {}
    conflicts: List[str] = []

    all_targets: Sequence[str] = (*COLLECTION_NAMES, COUNTERS_COLLECTION)

    for name in all_targets:
        if name not in existing:
            try:
                db.create_collection(name)
                created_collections.append(name)
            except CollectionInvalid:
                existing_collections.append(name)
        else:
            existing_collections.append(name)

    for name in COLLECTION_NAMES:
        coll_conflicts = check_unique_index_conflicts(db, name)
        conflicts.extend(coll_conflicts)

    if conflicts:
        raise RuntimeError(
            "Unique index conflict(s) detected in existing MongoDB data: " + "; ".join(conflicts)
        )

    for name in COLLECTION_NAMES:
        specs = COLLECTION_INDEXES.get(name, ())
        models = [spec.to_index_model() for spec in specs]
        if models:
            try:
                created_names = db[name].create_indexes(models)
                index_summary[name] = len(created_names)
            except OperationFailure as exc:
                raise RuntimeError(
                    f"Failed creating indexes for collection '{name}': {exc}"
                ) from exc

    counters_initialized = 0
    if initialize_counters:
        for name in COLLECTION_NAMES:
            max_doc = db[name].find_one(
                {"id": {"$type": "number"}},
                sort=[("id", -1)],
                projection={"id": 1},
            )
            max_id = int(max_doc["id"]) if max_doc and "id" in max_doc else 0
            sync_counter(db, name, max_id)
            counters_initialized += 1

    return {
        "created_collections": created_collections,
        "existing_collections": existing_collections,
        "total_app_collections": len(COLLECTION_NAMES),
        "indexes_ensured": index_summary,
        "counters_initialized": counters_initialized,
    }
