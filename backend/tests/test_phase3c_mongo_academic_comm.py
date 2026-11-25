import io
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models.quiz import AnswerOption, Question
from app.mongodb import get_mongo_database
from app.repositories.assignment_repository import create_submission_doc
from app.repositories.communication_repository import create_email_delivery_doc
from app.routers import admin as admin_router
from app.routers import courses as courses_router
from app.schemas.announcement import AnnouncementCreate
from app.schemas.assignment import AssignmentCreate
from app.schemas.quiz import AnswerOptionCreate, QuestionCreate, QuizCreate
from app.services import (
    announcement_service,
    assignment_service,
    email_service,
    notification_service,
    quiz_service,
)


def _auth_headers(client, email: str, password: str = "EduVerseDemo2026!") -> dict:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_mongo_quizzes_and_course_section_lesson_relationships(client, request):
    mongo_db = get_mongo_database()
    sarah_h = _auth_headers(client, "sarah.chen@eduverse.io")
    alex_h = _auth_headers(client, "alex.rivera@eduverse.io")
    admin_h = _auth_headers(client, "admin@eduverse.io")

    sqlite_db = SessionLocal()
    try:
        legacy_question = sqlite_db.query(Question).order_by(Question.id).first()
        max_option_id = sqlite_db.query(AnswerOption.id).order_by(AnswerOption.id.desc()).first()
        assert legacy_question is not None
        legacy_question_id = int(legacy_question.id)
        legacy_option_id = (max_option_id[0] if max_option_id else 0) + 1
    finally:
        sqlite_db.close()

    def cleanup_legacy_option() -> None:
        cleanup_db = SessionLocal()
        try:
            cleanup_db.query(AnswerOption).filter(
                AnswerOption.id == legacy_option_id
            ).delete(synchronize_session=False)
            cleanup_db.commit()
        finally:
            cleanup_db.close()

    request.addfinalizer(cleanup_legacy_option)
    sqlite_db = SessionLocal()
    try:
        sqlite_db.add(
            AnswerOption(
                id=legacy_option_id,
                question_id=legacy_question_id,
                option_text="Legacy SQLite-only option",
                is_correct=False,
                order_index=99,
            )
        )
        sqlite_db.commit()
    finally:
        sqlite_db.close()

    # Create course 1 section & lesson + a second course with its own section & lesson
    c1 = client.post(
        "/api/v1/instructor/courses",
        json={
            "title": f"Phase3C Quiz Course {uuid4().hex[:6]}",
            "description": "Course testing quiz-section-lesson links in MongoDB.",
            "category": "Architecture",
            "difficulty": "Intermediate",
            "is_published": True,
        },
        headers=sarah_h,
    ).json()
    c1_id = c1["id"]

    c2 = client.post(
        "/api/v1/instructor/courses",
        json={
            "title": f"Phase3C Foreign Course {uuid4().hex[:6]}",
            "description": "Second course used for cross-course relationship validation.",
            "category": "Architecture",
            "difficulty": "Beginner",
            "is_published": True,
        },
        headers=sarah_h,
    ).json()
    c2_id = c2["id"]

    sec1 = client.post(
        f"/api/v1/instructor/courses/{c1_id}/sections",
        json={"title": "Sec 1", "description": "Own section", "order_index": 1},
        headers=sarah_h,
    ).json()
    les1 = client.post(
        f"/api/v1/instructor/courses/{c1_id}/lessons",
        json={
            "title": "Lesson 1",
            "content": "Lesson 1 content for quiz link test.",
            "order_index": 1,
            "section_id": sec1["id"],
        },
        headers=sarah_h,
    ).json()

    foreign_sec = client.post(
        f"/api/v1/instructor/courses/{c2_id}/sections",
        json={"title": "Foreign Sec", "description": "Belongs to c2", "order_index": 1},
        headers=sarah_h,
    ).json()
    foreign_les = client.post(
        f"/api/v1/instructor/courses/{c2_id}/lessons",
        json={
            "title": "Foreign Lesson",
            "content": "Belongs to c2",
            "order_index": 1,
            "section_id": foreign_sec["id"],
        },
        headers=sarah_h,
    ).json()

    # Cross-course section_id or lesson_id rejected with 400
    bad_sec_quiz = client.post(
        f"/api/v1/instructor/courses/{c1_id}/quizzes",
        json={"title": "Bad Sec Quiz", "section_id": foreign_sec["id"], "questions": []},
        headers=sarah_h,
    )
    assert bad_sec_quiz.status_code == 400

    bad_les_quiz = client.post(
        f"/api/v1/instructor/courses/{c1_id}/quizzes",
        json={"title": "Bad Les Quiz", "lesson_id": foreign_les["id"], "questions": []},
        headers=sarah_h,
    )
    assert bad_les_quiz.status_code == 400

    # Valid quiz connected to course, section, and lesson
    created = client.post(
        f"/api/v1/instructor/courses/{c1_id}/quizzes",
        json={
            "title": "Mongo Linked Quiz",
            "description": "Linked to section and lesson",
            "passing_score": 50,
            "is_published": False,
            "section_id": sec1["id"],
            "lesson_id": les1["id"],
            "questions": [
                {
                    "question_text": "Initial Question 1?",
                    "order_index": 1,
                    "points": 10,
                    "options": [
                        {"option_text": "Right", "is_correct": True},
                        {"option_text": "Wrong", "is_correct": False},
                    ],
                }
            ],
        },
        headers=sarah_h,
    )
    assert created.status_code == 201, created.text
    created_option_ids = [
        option["id"]
        for question in created.json()["questions"]
        for option in question["options"]
    ]
    assert created_option_ids and min(created_option_ids) > legacy_option_id

    sqlite_check = SessionLocal()
    try:
        persisted_legacy_option = sqlite_check.query(AnswerOption).filter(
            AnswerOption.id == legacy_option_id
        ).one()
        assert persisted_legacy_option.option_text == "Legacy SQLite-only option"
    finally:
        sqlite_check.close()

    quiz_id = created.json()["id"]
    quiz_doc = mongo_db["quizzes"].find_one({"id": quiz_id})
    assert quiz_doc["course_id"] == c1_id
    assert quiz_doc["section_id"] == sec1["id"]
    assert quiz_doc["lesson_id"] == les1["id"]

    # Add, update, and remove a question in MongoDB
    q2_res = client.post(
        f"/api/v1/instructor/quizzes/{quiz_id}/questions",
        json={
            "question_text": "Second Question?",
            "order_index": 2,
            "points": 5,
            "options": [
                {"option_text": "True", "is_correct": True},
                {"option_text": "False", "is_correct": False},
            ],
        },
        headers=sarah_h,
    )
    assert q2_res.status_code == 201
    q2_id = q2_res.json()["id"]
    assert mongo_db["questions"].find_one({"id": q2_id})["quiz_id"] == quiz_id

    q2_upd = client.put(
        f"/api/v1/instructor/questions/{q2_id}",
        json={
            "question_text": "Updated Second Question?",
            "order_index": 2,
            "points": 10,
            "options": [
                {"option_text": "No", "is_correct": False},
                {"option_text": "Yes", "is_correct": True},
            ],
        },
        headers=sarah_h,
    )
    assert q2_upd.status_code == 200
    assert q2_upd.json()["points"] == 10

    assert (
        client.delete(f"/api/v1/instructor/questions/{q2_id}", headers=sarah_h).status_code
        == 200
    )
    assert mongo_db["questions"].find_one({"id": q2_id}) is None
    assert mongo_db["answer_options"].count_documents({"question_id": q2_id}) == 0

    # Publish & verify course detail + admin course count read MongoDB
    assert (
        client.patch(f"/api/v1/instructor/quizzes/{quiz_id}/publish", headers=sarah_h).status_code
        == 200
    )

    detail = client.get(f"/api/v1/courses/{c1_id}", headers=sarah_h).json()
    assert any(q["id"] == quiz_id and q["question_count"] == 1 for q in detail["quizzes"])

    admin_courses = client.get(
        f"/api/v1/admin/courses?search={c1['title']}", headers=admin_h
    ).json()["items"]
    assert any(item["id"] == c1_id and item["quiz_count"] == 1 for item in admin_courses)

    # Enroll Alex + approve + take quiz
    enr = client.post(f"/api/v1/courses/{c1_id}/enroll", headers=alex_h).json()
    client.post(f"/api/v1/instructor/enrollments/{enr['id']}/approve", headers=sarah_h)

    q_list = client.get(f"/api/v1/quizzes/course/{c1_id}", headers=alex_h)
    assert q_list.status_code == 200
    q1 = q_list.json()[0]["questions"][0]
    right_opt_id = q1["options"][0]["id"]

    sub = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        json={"answers": {str(q1["id"]): right_opt_id}},
        headers=alex_h,
    )
    assert sub.status_code == 200
    attempt_id = sub.json()["attempt_id"]
    assert sub.json()["passed"] is True
    assert mongo_db["quiz_attempts"].find_one({"id": attempt_id})["quiz_id"] == quiz_id
    assert mongo_db["quiz_attempt_answers"].count_documents({"attempt_id": attempt_id}) == 1

    history = client.get(f"/api/v1/quizzes/my-history?quiz_id={quiz_id}", headers=alex_h)
    assert history.status_code == 200
    assert any(a["id"] == attempt_id for a in history.json())

    # Cleanup courses (cascades quizzes, questions, options, enrollments)
    client.delete(f"/api/v1/instructor/courses/{c1_id}", headers=sarah_h)
    client.delete(f"/api/v1/instructor/courses/{c2_id}", headers=sarah_h)
    assert mongo_db["quizzes"].find_one({"id": quiz_id}) is None


def test_mongo_assignments_attachments_and_duplicate_prevention(client):
    mongo_db = get_mongo_database()
    sarah_h = _auth_headers(client, "sarah.chen@eduverse.io")
    alex_h = _auth_headers(client, "alex.rivera@eduverse.io")
    admin_h = _auth_headers(client, "admin@eduverse.io")

    # Cross-course section_id rejected
    bad_assign = client.post(
        "/api/v1/instructor/courses/1/assignments",
        json={
            "title": "Invalid Section Assignment",
            "instructions": "Must fail because section 999999 does not exist in course 1.",
            "section_id": 999999,
        },
        headers=sarah_h,
    )
    assert bad_assign.status_code == 400

    # Create & publish assignment on Course 1
    created = client.post(
        "/api/v1/instructor/courses/1/assignments",
        json={
            "title": f"Mongo Assignment {uuid4().hex[:6]}",
            "description": "MongoDB assignment test",
            "instructions": "Upload notes and submit concise architectural summary.",
            "max_marks": 100,
            "is_published": True,
        },
        headers=sarah_h,
    )
    assert created.status_code == 201
    aid = created.json()["id"]
    assert mongo_db["assignments"].find_one({"id": aid})["course_id"] == 1

    # Admin course listing counts MongoDB assignment
    admin_c1 = client.get("/api/v1/admin/courses?page_size=50", headers=admin_h).json()["items"]
    c1_row = next(r for r in admin_c1 if r["id"] == 1)
    assert c1_row["assignment_count"] >= 3

    # Upload student attachment
    att_res = client.post(
        f"/api/v1/assignments/{aid}/attachments",
        files={"file": ("notes.txt", io.BytesIO(b"Student clean text notes."), "text/plain")},
        headers=alex_h,
    )
    assert att_res.status_code == 201
    assert att_res.json()["name"] == "notes.txt"

    # Submit, grade, and check MongoDB doc
    sub_res = client.post(
        f"/api/v1/assignments/{aid}/submit",
        json={"submission_text": "My architectural writeup stored in MongoDB."},
        headers=alex_h,
    )
    assert sub_res.status_code == 200
    sub_id = sub_res.json()["id"]
    assert mongo_db["assignment_submissions"].find_one({"id": sub_id})["assignment_id"] == aid

    # Unique constraint on (assignment_id, student_id) prevents duplicate submission docs
    alex_doc = mongo_db["users"].find_one({"email": "alex.rivera@eduverse.io"})
    with pytest.raises(HTTPException) as exc_info:
        create_submission_doc(
            mongo_db,
            assignment_id=aid,
            student_id=int(alex_doc["id"]),
            submission_text="Duplicate direct insert",
            attachments_json=None,
            is_late=False,
        )
    assert exc_info.value.status_code == 409

    grade_res = client.put(
        f"/api/v1/instructor/submissions/{sub_id}/grade",
        json={"grade": 92.5, "feedback": "Well done!"},
        headers=sarah_h,
    )
    assert grade_res.status_code == 200
    assert grade_res.json()["grade"] == 92.5
    assert mongo_db["assignment_submissions"].find_one({"id": sub_id})["status"] == "graded"

    # Archive & clean up
    arch = client.patch(f"/api/v1/instructor/assignments/{aid}/archive", headers=sarah_h)
    assert arch.status_code == 200
    assert arch.json()["is_archived"] is True


def test_mongo_learning_materials_and_course_detail_outline(client):
    mongo_db = get_mongo_database()
    sarah_h = _auth_headers(client, "sarah.chen@eduverse.io")
    alex_h = _auth_headers(client, "alex.rivera@eduverse.io")

    # Invalid lesson link -> 400
    bad_mat = client.post(
        "/api/v1/instructor/courses/1/materials",
        data={"title": "Bad Lesson Link", "lesson_id": "999999"},
        files={"file": ("note.txt", io.BytesIO(b"Plain text content."), "text/plain")},
        headers=sarah_h,
    )
    assert bad_mat.status_code == 400

    # Valid material upload
    up = client.post(
        "/api/v1/instructor/courses/1/materials",
        data={"title": "Mongo Syllabus Notes", "description": "Stored in MongoDB"},
        files={"file": ("syllabus.txt", io.BytesIO(b"Syllabus summary content."), "text/plain")},
        headers=sarah_h,
    )
    assert up.status_code == 201
    mat_id = up.json()["id"]
    assert mongo_db["learning_materials"].find_one({"id": mat_id})["course_id"] == 1

    # Course detail (MongoDB-only path) includes uploaded material for enrolled Alex
    detail = client.get("/api/v1/courses/1", headers=alex_h).json()
    assert any(m["id"] == mat_id for m in detail["materials"])

    # Delete removes MongoDB record
    assert client.delete(f"/api/v1/instructor/materials/{mat_id}", headers=sarah_h).status_code == 200
    assert mongo_db["learning_materials"].find_one({"id": mat_id}) is None


def test_mongo_announcements_discussions_and_notification_deletion(client, monkeypatch):
    mongo_db = get_mongo_database()
    monkeypatch.setattr(courses_router, "send_email_delivery", lambda *args: "sent")

    sarah_h = _auth_headers(client, "sarah.chen@eduverse.io")
    alex_h = _auth_headers(client, "alex.rivera@eduverse.io")
    marcus_h = _auth_headers(client, "marcus.vance@eduverse.io")

    # Register a pending (unapproved) student on Course 1 to verify they do NOT receive announcement notifications
    pending_email = f"pending.notif.{uuid4().hex[:6]}@eduverse.io"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": pending_email, "full_name": "Pending Student", "password": "StrongPassword123!"},
    )
    assert reg.status_code == 201
    pending_id = reg.json()["id"]
    pending_h = _auth_headers(client, pending_email, "StrongPassword123!")
    assert client.post("/api/v1/courses/1/enroll", headers=pending_h).status_code == 201

    # Instructor creates draft announcement -> zero notifications sent
    alex_doc = mongo_db["users"].find_one({"email": "alex.rivera@eduverse.io"})
    alex_id = int(alex_doc["id"])
    alex_notifs_before = mongo_db["notifications"].count_documents({"user_id": alex_id})

    draft_ann = client.post(
        "/api/v1/courses/1/announcements",
        json={"title": "Draft Only", "content": "Not yet visible to students.", "is_published": False},
        headers=sarah_h,
    )
    assert draft_ann.status_code == 201
    ann_id = draft_ann.json()["id"]
    assert mongo_db["notifications"].count_documents({"user_id": alex_id}) == alex_notifs_before

    # Transition draft -> published notifies Alex, NOT pending_id
    upd_ann = client.put(
        f"/api/v1/announcements/{ann_id}",
        json={"is_published": True},
        headers=sarah_h,
    )
    assert upd_ann.status_code == 200
    assert mongo_db["notifications"].count_documents({"user_id": alex_id}) == alex_notifs_before + 1
    assert mongo_db["notifications"].count_documents({"user_id": pending_id}) == 0

    # Alex gets newest notification, Marcus cannot delete it (403), Alex deletes it (200)
    newest = client.get("/api/v1/notifications?limit=1", headers=alex_h).json()[0]
    nid = newest["id"]
    assert client.delete(f"/api/v1/notifications/{nid}", headers=marcus_h).status_code == 403
    del_notif = client.delete(f"/api/v1/notifications/{nid}", headers=alex_h)
    assert del_notif.status_code == 200
    assert mongo_db["notifications"].find_one({"id": nid}) is None

    # Deleting again returns 404
    assert client.delete(f"/api/v1/notifications/{nid}", headers=alex_h).status_code == 404

    # Cleanup draft announcement & pending enrollment
    assert client.delete(f"/api/v1/announcements/{ann_id}", headers=sarah_h).status_code == 200
    assert mongo_db["course_announcements"].find_one({"id": ann_id}) is None
    client.delete("/api/v1/courses/1/enroll", headers=pending_h)


def test_mongo_email_deliveries_admin_list_retry_and_duplicate_protection(client, monkeypatch):
    mongo_db = get_mongo_database()
    email = f"delivery.{uuid4().hex[:8]}@eduverse.io"
    assert (
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "full_name": "Delivery Student", "password": "StrongPassword123!"},
        ).status_code
        == 201
    )
    student_h = _auth_headers(client, email, "StrongPassword123!")
    admin_h = _auth_headers(client, "admin@eduverse.io")

    # Configure SMTP settings & force failure on first send
    for key, value in {
        "EMAIL_HOST_USER": "mailer@example.com",
        "EMAIL_HOST_PASSWORD": "fake-app-password",
        "DEFAULT_FROM_EMAIL": "mailer@example.com",
        "EMAIL_USE_TLS": True,
    }.items():
        monkeypatch.setattr(courses_router.settings, key, value)
        monkeypatch.setattr(admin_router.settings, key, value)

    monkeypatch.setattr(
        email_service,
        "_send_smtp_message",
        lambda *args: (_ for _ in ()).throw(TimeoutError("simulated timeout")),
    )

    enroll_res = client.post("/api/v1/courses/1/enroll", headers=student_h)
    assert enroll_res.status_code == 201
    delivery_id = enroll_res.json()["email_delivery_id"]
    enr_id = enroll_res.json()["id"]

    delivery_doc = mongo_db["email_deliveries"].find_one({"id": delivery_id})
    assert delivery_doc["status"] == "failed"
    assert delivery_doc["attempts"] == 1

    # Unique index uq_email_delivery_enrollment_event prevents duplicate event for same enrollment
    with pytest.raises(HTTPException) as dup_exc:
        create_email_delivery_doc(
            mongo_db,
            enrollment_id=enr_id,
            event_type=email_service.ENROLLMENT_REQUEST,
            recipient_email="sarah.chen@eduverse.io",
        )
    assert dup_exc.value.status_code == 409

    # Admin list failed deliveries reads MongoDB
    listed = client.get("/api/v1/admin/email/deliveries?status=failed", headers=admin_h)
    assert listed.status_code == 200
    assert any(d["id"] == delivery_id for d in listed.json())

    # Retry succeeds and updates MongoDB doc
    monkeypatch.setattr(email_service, "_send_smtp_message", lambda *args: None)
    retry = client.post(f"/api/v1/admin/email/deliveries/{delivery_id}/retry", headers=admin_h)
    assert retry.status_code == 200
    updated_doc = mongo_db["email_deliveries"].find_one({"id": delivery_id})
    assert updated_doc["status"] == "sent"
    assert updated_doc["attempts"] == 2

    # Unenroll cleans up enrollment + delivery
    client.delete("/api/v1/courses/1/enroll", headers=student_h)


def test_phase3c_rollback_when_sqlite_shadow_fails(monkeypatch):
    mongo_db = get_mongo_database()

    def fail_shadow(*args, **kwargs):
        raise SQLAlchemyError("simulated sqlite shadow error")

    sarah = mongo_db["users"].find_one({"email": "sarah.chen@eduverse.io"})
    from app.repositories.user_repository import MongoUser

    sarah_user = MongoUser.from_doc(sarah)

    # Quiz rollback
    quiz_title = f"Rollback Quiz {uuid4().hex[:6]}"
    monkeypatch.setattr(quiz_service, "sync_quiz_to_sqlite_shadow", fail_shadow)
    sqlite_db = SessionLocal()
    try:
        with pytest.raises(SQLAlchemyError):
            quiz_service.create_instructor_quiz(
                mongo_db,
                1,
                QuizCreate(
                    title=quiz_title,
                    questions=[
                        QuestionCreate(
                            question_text="Will this rollback?",
                            options=[
                                AnswerOptionCreate(option_text="Yes", is_correct=True),
                                AnswerOptionCreate(option_text="No", is_correct=False),
                            ],
                        )
                    ],
                ),
                sarah_user,
                sqlite_db=sqlite_db,
            )
    finally:
        sqlite_db.close()
    assert mongo_db["quizzes"].find_one({"title": quiz_title}) is None

    # Assignment rollback
    assign_title = f"Rollback Assignment {uuid4().hex[:6]}"
    monkeypatch.setattr(assignment_service, "sync_assignment_to_sqlite_shadow", fail_shadow)
    with pytest.raises(SQLAlchemyError):
        assignment_service.create_assignment(
            mongo_db,
            1,
            AssignmentCreate(
                title=assign_title,
                instructions="Must compensate MongoDB on shadow sync failure.",
            ),
            sarah_user,
            sqlite_db=object(),  # type: ignore[arg-type]
        )
    assert mongo_db["assignments"].find_one({"title": assign_title}) is None

    # Announcement rollback
    ann_title = f"Rollback Announcement {uuid4().hex[:6]}"
    monkeypatch.setattr(announcement_service, "sync_announcement_to_sqlite_shadow", fail_shadow)
    with pytest.raises(SQLAlchemyError):
        announcement_service.create_announcement(
            mongo_db,
            1,
            AnnouncementCreate(title=ann_title, content="Rollback announcement test."),
            sarah_user,
            sqlite_db=object(),  # type: ignore[arg-type]
        )
    assert mongo_db["course_announcements"].find_one({"title": ann_title}) is None

    # Notification rollback
    notif_title = f"Rollback Notif {uuid4().hex[:6]}"
    monkeypatch.setattr(notification_service, "sync_notification_to_sqlite_shadow", fail_shadow)
    with pytest.raises(SQLAlchemyError):
        notification_service.create_notification(
            mongo_db,
            sarah_user.id,
            notif_title,
            "Should rollback.",
            "system",
            sqlite_db=object(),  # type: ignore[arg-type]
        )
    assert mongo_db["notifications"].find_one({"title": notif_title}) is None
