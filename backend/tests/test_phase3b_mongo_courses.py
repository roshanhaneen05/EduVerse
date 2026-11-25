from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.mongo_schema import COUNTERS_COLLECTION, next_sequence_id
from app.mongodb import get_mongo_database
from app.routers import courses as courses_router
from app.routers import instructor as instructor_router
from app.repositories.course_repository import create_course_doc, delete_course_cascade_mongo
from app.schemas.course import CourseCreate
from app.services import course_service


def _auth_headers(client, email: str, password: str = "EduVerseDemo2026!") -> dict:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_mongo_course_section_lesson_lifecycle_and_permissions(client):
    mongo_db = get_mongo_database()
    sarah_h = _auth_headers(client, "sarah.chen@eduverse.io")
    marcus_h = _auth_headers(client, "marcus.vance@eduverse.io")
    alex_h = _auth_headers(client, "alex.rivera@eduverse.io")

    # 1. Create course in MongoDB
    before_course_seq = mongo_db[COUNTERS_COLLECTION].find_one({"_id": "courses"})["seq"]
    created = client.post(
        "/api/v1/instructor/courses",
        json={
            "title": f"MongoDB Course {uuid4().hex[:6]}",
            "description": "End-to-end course persisted in MongoDB Atlas.",
            "category": "Databases",
            "difficulty": "Intermediate",
            "is_published": False,
        },
        headers=sarah_h,
    )
    assert created.status_code == 201
    course = created.json()
    course_id = course["id"]
    assert course_id == before_course_seq + 1
    assert mongo_db["courses"].find_one({"id": course_id})["title"] == course["title"]

    # Student cannot enroll in unpublished course
    unpub_enroll = client.post(f"/api/v1/courses/{course_id}/enroll", headers=alex_h)
    assert unpub_enroll.status_code == 400

    # Other instructor cannot modify or delete Sarah's course
    assert (
        client.put(
            f"/api/v1/instructor/courses/{course_id}",
            json={"title": "Hijacked Title"},
            headers=marcus_h,
        ).status_code
        == 403
    )
    assert client.delete(f"/api/v1/instructor/courses/{course_id}", headers=marcus_h).status_code == 403

    # Update & publish course
    updated = client.put(
        f"/api/v1/instructor/courses/{course_id}",
        json={"difficulty": "Advanced"},
        headers=sarah_h,
    )
    assert updated.status_code == 200
    assert updated.json()["difficulty"] == "Advanced"

    pub = client.patch(f"/api/v1/instructor/courses/{course_id}/publish", headers=sarah_h)
    assert pub.status_code == 200
    assert pub.json()["is_published"] is True

    # 2. Section management in MongoDB
    sec = client.post(
        f"/api/v1/instructor/courses/{course_id}/sections",
        json={"title": "Mongo Section 1", "description": "Intro section", "order_index": 1},
        headers=sarah_h,
    )
    assert sec.status_code == 201
    sec_id = sec.json()["id"]
    assert mongo_db["course_sections"].find_one({"id": sec_id})["course_id"] == course_id

    # Invalid cross-course section reference when adding lesson -> 400
    bad_lesson = client.post(
        f"/api/v1/instructor/courses/{course_id}/lessons",
        json={
            "title": "Invalid Section Lesson",
            "content": "Should fail due to invalid section reference.",
            "order_index": 1,
            "section_id": 999999,
        },
        headers=sarah_h,
    )
    assert bad_lesson.status_code == 400

    # 3. Lesson creation & deletion in MongoDB
    lesson = client.post(
        f"/api/v1/instructor/courses/{course_id}/lessons",
        json={
            "title": "Lesson 1 in MongoDB",
            "content": "Detailed lesson content stored in MongoDB.",
            "order_index": 1,
            "section_id": sec_id,
        },
        headers=sarah_h,
    )
    assert lesson.status_code == 201
    lesson_id = lesson.json()["id"]
    assert mongo_db["lessons"].find_one({"id": lesson_id})["section_id"] == sec_id

    # 4. Cascade delete course cleans up sections, lessons, and course in MongoDB
    deleted = client.delete(f"/api/v1/instructor/courses/{course_id}", headers=sarah_h)
    assert deleted.status_code == 200
    assert mongo_db["courses"].find_one({"id": course_id}) is None
    assert mongo_db["course_sections"].find_one({"id": sec_id}) is None
    assert mongo_db["lessons"].find_one({"id": lesson_id}) is None


def test_course_delete_cascades_linked_records_and_preserves_other_courses(request):
    mongo_db = get_mongo_database()
    created_ids: dict[str, list[int]] = {}

    def add(collection: str, **fields) -> int:
        doc_id = next_sequence_id(mongo_db, collection)
        mongo_db[collection].insert_one({"id": doc_id, **fields})
        created_ids.setdefault(collection, []).append(doc_id)
        return doc_id

    def cleanup_test_records() -> None:
        for collection, ids in created_ids.items():
            mongo_db[collection].delete_many({"id": {"$in": ids}})

    request.addfinalizer(cleanup_test_records)

    instructor = mongo_db["users"].find_one({"role": "instructor"}, {"id": 1})
    assert instructor is not None

    def add_course(title: str) -> int:
        course = create_course_doc(
            mongo_db,
            title=title,
            description="Course used by the MongoDB cascade integration test.",
            category="Testing",
            difficulty="Beginner",
            is_published=False,
            instructor_id=int(instructor["id"]),
        )
        created_ids.setdefault("courses", []).append(course.id)
        return course.id

    course_id = add_course("Cascade target")
    other_course_id = add_course("Unrelated course")

    section_id = add("course_sections", course_id=course_id)
    other_section_id = add("course_sections", course_id=other_course_id)
    lesson_id = add("lessons", course_id=course_id, section_id=section_id)
    other_lesson_id = add("lessons", course_id=other_course_id, section_id=other_section_id)
    progress_id = add("lesson_progress", student_id=91001, lesson_id=lesson_id)
    other_progress_id = add("lesson_progress", student_id=91002, lesson_id=other_lesson_id)

    enrollment_id = add("course_enrollments", student_id=91001, course_id=course_id)
    other_enrollment_id = add("course_enrollments", student_id=91002, course_id=other_course_id)
    delivery_id = add("email_deliveries", enrollment_id=enrollment_id, event_type="enrolled")
    other_delivery_id = add(
        "email_deliveries", enrollment_id=other_enrollment_id, event_type="enrolled"
    )

    quiz_id = add("quizzes", course_id=course_id)
    other_quiz_id = add("quizzes", course_id=other_course_id)
    question_id = add("questions", quiz_id=quiz_id)
    other_question_id = add("questions", quiz_id=other_quiz_id)
    option_id = add("answer_options", question_id=question_id)
    other_option_id = add("answer_options", question_id=other_question_id)
    attempt_id = add("quiz_attempts", quiz_id=quiz_id, student_id=91001)
    other_attempt_id = add("quiz_attempts", quiz_id=other_quiz_id, student_id=91002)
    attempt_answer_id = add(
        "quiz_attempt_answers", attempt_id=attempt_id, question_id=question_id
    )
    other_attempt_answer_id = add(
        "quiz_attempt_answers", attempt_id=other_attempt_id, question_id=other_question_id
    )

    assignment_id = add("assignments", course_id=course_id)
    other_assignment_id = add("assignments", course_id=other_course_id)
    submission_id = add(
        "assignment_submissions", assignment_id=assignment_id, student_id=91001
    )
    other_submission_id = add(
        "assignment_submissions", assignment_id=other_assignment_id, student_id=91002
    )
    rubric_id = add("assignment_rubrics", assignment_id=assignment_id)
    other_rubric_id = add("assignment_rubrics", assignment_id=other_assignment_id)
    rubric_criterion_id = add(
        "evaluation_criterion_rubrics", rubric_id=rubric_id, order_index=1
    )
    other_rubric_criterion_id = add(
        "evaluation_criterion_rubrics", rubric_id=other_rubric_id, order_index=1
    )
    evaluation_id = add(
        "assignment_evaluations",
        assignment_id=assignment_id,
        submission_id=submission_id,
    )
    other_evaluation_id = add(
        "assignment_evaluations",
        assignment_id=other_assignment_id,
        submission_id=other_submission_id,
    )
    evaluation_criterion_id = add(
        "assignment_evaluation_criteria", evaluation_id=evaluation_id, order_index=1
    )
    other_evaluation_criterion_id = add(
        "assignment_evaluation_criteria", evaluation_id=other_evaluation_id, order_index=1
    )

    material_id = add("learning_materials", course_id=course_id, storage_key=uuid4().hex)
    other_material_id = add(
        "learning_materials", course_id=other_course_id, storage_key=uuid4().hex
    )
    announcement_id = add("course_announcements", course_id=course_id)
    other_announcement_id = add("course_announcements", course_id=other_course_id)
    discussion_id = add("course_discussions", course_id=course_id)
    other_discussion_id = add("course_discussions", course_id=other_course_id)
    reply_id = add("discussion_replies", thread_id=discussion_id)
    other_reply_id = add("discussion_replies", thread_id=other_discussion_id)

    conversation_id = add("ai_conversations", user_id=91001, course_id=course_id)
    other_conversation_id = add("ai_conversations", user_id=91002, course_id=other_course_id)
    message_id = add("ai_messages", conversation_id=conversation_id)
    other_message_id = add("ai_messages", conversation_id=other_conversation_id)
    ai_quiz_id = add("ai_quizzes", student_id=91001, course_id=course_id)
    other_ai_quiz_id = add("ai_quizzes", student_id=91002, course_id=other_course_id)
    ai_question_id = add("ai_quiz_questions", quiz_id=ai_quiz_id, order_index=1)
    other_ai_question_id = add("ai_quiz_questions", quiz_id=other_ai_quiz_id, order_index=1)
    ai_option_id = add("ai_quiz_options", question_id=ai_question_id)
    other_ai_option_id = add("ai_quiz_options", question_id=other_ai_question_id)
    ai_attempt_id = add("ai_quiz_attempts", quiz_id=ai_quiz_id, student_id=91001)
    other_ai_attempt_id = add("ai_quiz_attempts", quiz_id=other_ai_quiz_id, student_id=91002)
    ai_answer_id = add(
        "ai_quiz_answers", attempt_id=ai_attempt_id, question_id=ai_question_id
    )
    other_ai_answer_id = add(
        "ai_quiz_answers", attempt_id=other_ai_attempt_id, question_id=other_ai_question_id
    )

    paper_id = add(
        "instructor_question_papers",
        instructor_id=91001,
        course_id=course_id,
        generation_hash=f"target-{uuid4().hex}",
    )
    other_paper_id = add(
        "instructor_question_papers",
        instructor_id=91001,
        course_id=other_course_id,
        generation_hash=f"other-{uuid4().hex}",
    )
    generated_question_id = add(
        "instructor_generated_questions", question_paper_id=paper_id, question_order=1
    )
    other_generated_question_id = add(
        "instructor_generated_questions", question_paper_id=other_paper_id, question_order=1
    )

    plan_id = add(
        "study_plans",
        student_id=91001,
        is_active=True,
        selected_course_ids=[course_id, other_course_id],
    )
    preference_id = add(
        "study_preferences",
        student_id=91001,
        selected_course_ids=[course_id, other_course_id],
        deadlines_json=[
            {"course_id": course_id, "title": "Target deadline"},
            {"course_id": other_course_id, "title": "Other deadline"},
        ],
    )
    deadline_id = add(
        "study_deadlines",
        plan_id=plan_id,
        student_id=91001,
        course_id=course_id,
    )
    other_deadline_id = add(
        "study_deadlines",
        plan_id=plan_id,
        student_id=91001,
        course_id=other_course_id,
    )
    task_id = add(
        "study_tasks",
        plan_id=plan_id,
        student_id=91001,
        course_id=course_id,
        lesson_id=lesson_id,
    )
    other_task_id = add(
        "study_tasks",
        plan_id=plan_id,
        student_id=91001,
        course_id=other_course_id,
        lesson_id=other_lesson_id,
    )
    task_notification_id = add(
        "study_notifications",
        notification_key=f"task-{uuid4().hex}",
        task_id=task_id,
    )
    deadline_notification_id = add(
        "study_notifications",
        notification_key=f"deadline-{uuid4().hex}",
        deadline_id=deadline_id,
    )
    other_notification_id = add(
        "study_notifications",
        notification_key=f"other-{uuid4().hex}",
        task_id=other_task_id,
        deadline_id=other_deadline_id,
    )

    delete_course_cascade_mongo(mongo_db, course_id)

    removed = {
        "courses": [course_id],
        "course_sections": [section_id],
        "lessons": [lesson_id],
        "lesson_progress": [progress_id],
        "course_enrollments": [enrollment_id],
        "email_deliveries": [delivery_id],
        "quizzes": [quiz_id],
        "questions": [question_id],
        "answer_options": [option_id],
        "quiz_attempt_answers": [attempt_answer_id],
        "assignments": [assignment_id],
        "assignment_submissions": [submission_id],
        "assignment_rubrics": [rubric_id],
        "evaluation_criterion_rubrics": [rubric_criterion_id],
        "assignment_evaluations": [evaluation_id],
        "assignment_evaluation_criteria": [evaluation_criterion_id],
        "learning_materials": [material_id],
        "course_announcements": [announcement_id],
        "course_discussions": [discussion_id],
        "discussion_replies": [reply_id],
        "ai_quizzes": [ai_quiz_id],
        "ai_quiz_questions": [ai_question_id],
        "ai_quiz_options": [ai_option_id],
        "ai_quiz_attempts": [ai_attempt_id],
        "ai_quiz_answers": [ai_answer_id],
        "instructor_question_papers": [paper_id],
        "instructor_generated_questions": [generated_question_id],
        "study_deadlines": [deadline_id],
        "study_tasks": [task_id],
        "study_notifications": [task_notification_id, deadline_notification_id],
    }
    for collection, ids in removed.items():
        for doc_id in ids:
            assert mongo_db[collection].find_one({"id": doc_id}) is None, (
                f"{collection} document {doc_id} should be removed"
            )

    preserved = {
        "courses": [other_course_id],
        "course_sections": [other_section_id],
        "lessons": [other_lesson_id],
        "lesson_progress": [other_progress_id],
        "course_enrollments": [other_enrollment_id],
        "email_deliveries": [other_delivery_id],
        "quizzes": [other_quiz_id],
        "questions": [other_question_id],
        "answer_options": [other_option_id],
        "quiz_attempts": [other_attempt_id],
        "quiz_attempt_answers": [other_attempt_answer_id],
        "assignments": [other_assignment_id],
        "assignment_submissions": [other_submission_id],
        "assignment_rubrics": [other_rubric_id],
        "evaluation_criterion_rubrics": [other_rubric_criterion_id],
        "assignment_evaluations": [other_evaluation_id],
        "assignment_evaluation_criteria": [other_evaluation_criterion_id],
        "learning_materials": [other_material_id],
        "course_announcements": [other_announcement_id],
        "course_discussions": [other_discussion_id],
        "discussion_replies": [other_reply_id],
        "ai_conversations": [conversation_id, other_conversation_id],
        "ai_messages": [message_id, other_message_id],
        "ai_quizzes": [other_ai_quiz_id],
        "ai_quiz_questions": [other_ai_question_id],
        "ai_quiz_options": [other_ai_option_id],
        "ai_quiz_attempts": [other_ai_attempt_id],
        "ai_quiz_answers": [other_ai_answer_id],
        "instructor_question_papers": [other_paper_id],
        "instructor_generated_questions": [other_generated_question_id],
        "study_notifications": [other_notification_id],
    }
    for collection, ids in preserved.items():
        for doc_id in ids:
            assert mongo_db[collection].find_one({"id": doc_id}) is not None, (
                f"{collection} document {doc_id} should be preserved"
            )

    assert mongo_db["quiz_attempts"].find_one({"id": attempt_id})["quiz_id"] is None
    assert mongo_db["ai_conversations"].find_one({"id": conversation_id})["course_id"] is None
    assert mongo_db["ai_conversations"].find_one({"id": other_conversation_id})["course_id"] == (
        other_course_id
    )
    preference = mongo_db["study_preferences"].find_one({"id": preference_id})
    assert preference["selected_course_ids"] == [other_course_id]
    assert preference["deadlines_json"] == [
        {"course_id": other_course_id, "title": "Other deadline"}
    ]
    assert mongo_db["study_plans"].find_one({"id": plan_id})["selected_course_ids"] == [
        other_course_id
    ]


def test_mongo_enrollment_progress_and_unenroll_flow(client, monkeypatch):
    mongo_db = get_mongo_database()
    monkeypatch.setattr(courses_router, "send_email_delivery", lambda *args: "sent")
    monkeypatch.setattr(instructor_router, "send_email_delivery", lambda *args: "sent")

    sarah_h = _auth_headers(client, "sarah.chen@eduverse.io")
    email = f"phase3b.{uuid4().hex[:8]}@eduverse.io"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Phase3B Student", "password": "StrongPassword123!"},
    )
    assert reg.status_code == 201
    student_id = reg.json()["id"]
    student_h = _auth_headers(client, email, "StrongPassword123!")

    # Create a dedicated 2-lesson published course for deterministic completion calculation
    course_res = client.post(
        "/api/v1/instructor/courses",
        json={
            "title": f"Progress Course {uuid4().hex[:6]}",
            "description": "Course for verifying MongoDB enrollment and lesson progress.",
            "category": "Engineering",
            "difficulty": "Beginner",
            "is_published": True,
        },
        headers=sarah_h,
    )
    course_id = course_res.json()["id"]
    l1 = client.post(
        f"/api/v1/instructor/courses/{course_id}/lessons",
        json={"title": "L1", "content": "First lesson body content.", "order_index": 1},
        headers=sarah_h,
    ).json()["id"]
    l2 = client.post(
        f"/api/v1/instructor/courses/{course_id}/lessons",
        json={"title": "L2", "content": "Second lesson body content.", "order_index": 2},
        headers=sarah_h,
    ).json()["id"]

    # Enroll -> pending in MongoDB; duplicate -> 409
    enr = client.post(f"/api/v1/courses/{course_id}/enroll", headers=student_h)
    assert enr.status_code == 201
    enr_id = enr.json()["id"]
    assert mongo_db["course_enrollments"].find_one({"id": enr_id})["status"] == "pending"
    assert client.post(f"/api/v1/courses/{course_id}/enroll", headers=student_h).status_code == 409

    # Pending student cannot access lesson or complete it
    assert client.get(f"/api/v1/lessons/{l1}", headers=student_h).status_code == 403
    assert client.post(f"/api/v1/lessons/{l1}/complete", headers=student_h).status_code == 403

    # Approve enrollment
    app_res = client.post(f"/api/v1/instructor/enrollments/{enr_id}/approve", headers=sarah_h)
    assert app_res.status_code == 200
    assert mongo_db["course_enrollments"].find_one({"id": enr_id})["status"] == "approved"

    # Complete lesson 1 -> 50.0%, complete lesson 2 -> 100.0%
    p1 = client.post(f"/api/v1/lessons/{l1}/complete", headers=student_h)
    assert p1.status_code == 200
    assert p1.json()["course_completion_percentage"] == 50.0
    assert (
        mongo_db["lesson_progress"].find_one({"student_id": student_id, "lesson_id": l1})[
            "is_completed"
        ]
        is True
    )

    p2 = client.post(f"/api/v1/lessons/{l2}/complete", headers=student_h)
    assert p2.status_code == 200
    assert p2.json()["course_completion_percentage"] == 100.0
    assert mongo_db["course_enrollments"].find_one({"id": enr_id})["completion_percentage"] == 100.0

    # Course detail reflects 100% completion and completed flags
    detail = client.get(f"/api/v1/courses/{course_id}", headers=student_h).json()
    assert detail["is_enrolled"] is True
    assert detail["completion_percentage"] == 100.0
    assert all(item["is_completed"] is True for item in detail["lessons"])

    # Unenroll removes enrollment from MongoDB
    unenr = client.delete(f"/api/v1/courses/{course_id}/enroll", headers=student_h)
    assert unenr.status_code == 200
    assert mongo_db["course_enrollments"].find_one({"id": enr_id}) is None

    # Clean up test course
    client.delete(f"/api/v1/instructor/courses/{course_id}", headers=sarah_h)


def test_course_creation_rolls_back_mongodb_when_sqlite_shadow_fails(monkeypatch):
    mongo_db = get_mongo_database()
    title = f"Rollback Course {uuid4().hex[:8]}"

    def fail_shadow(*args, **kwargs):
        raise SQLAlchemyError("simulated sqlite failure")

    monkeypatch.setattr(course_service, "sync_course_to_sqlite_shadow", fail_shadow)

    with pytest.raises(SQLAlchemyError):
        course_service.create_course(
            mongo_db,
            CourseCreate(
                title=title,
                description="Course used to test MongoDB rollback compensation.",
                category="Testing",
                difficulty="Beginner",
            ),
            instructor_id=2,
            sqlite_db=object(),  # type: ignore[arg-type]
        )

    assert mongo_db["courses"].find_one({"title": title}) is None
