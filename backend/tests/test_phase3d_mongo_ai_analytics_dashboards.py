from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from app.config import get_settings
from app.database import SessionLocal
from app.models.ai import AIConversation, AIMessage
from app.models.ai_learning import AIQuiz, AIQuizAttempt, StudyPlan, StudyTask
from app.models.instructor_ai import AssignmentEvaluation, AssignmentRubric, QuestionPaper
from app.mongodb import get_mongo_database
from app.repositories.course_repository import (
    create_course_doc,
    create_enrollment_doc,
    create_lesson_doc,
    create_section_doc,
    sync_course_to_sqlite_shadow,
    sync_enrollment_to_sqlite_shadow,
    sync_lesson_to_sqlite_shadow,
    sync_section_to_sqlite_shadow,
)
from app.repositories.quiz_repository import (
    create_quiz_attempt_doc,
    create_quiz_doc,
    sync_quiz_attempt_to_sqlite_shadow,
    sync_quiz_to_sqlite_shadow,
)
from app.repositories.user_repository import get_user_by_email


def _login(client, email: str, password: str = "EduVerseDemo2026!") -> dict:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _register_student(client) -> tuple[str, dict]:
    email = f"phase3d-{uuid4().hex[:10]}@eduverse.io"
    password = "StrongPassword123!"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Phase 3D Student"},
    )
    assert reg.status_code == 201, reg.text
    return email, _login(client, email, password)


def test_phase3d_test_database_isolation():
    settings = get_settings()
    assert settings.MONGODB_DATABASE != "eduverse"
    assert settings.MONGODB_DATABASE == "eduverse_test"


def test_phase3d_ai_tutor_conversations_and_failed_quiz_recommendations(client, monkeypatch):
    mongo_db = get_mongo_database()
    sql_db = SessionLocal()
    try:
        email, student_headers = _register_student(client)
        student = get_user_by_email(mongo_db, email)
        instructor = get_user_by_email(mongo_db, "sarah.chen@eduverse.io")
        assert student is not None and instructor is not None

        course = create_course_doc(
            mongo_db,
            title=f"Phase3D Tutor Course {uuid4().hex[:6]}",
            description="Course for AI tutor verification.",
            category="Data Science",
            difficulty="Intermediate",
            instructor_id=instructor.id,
            is_published=True,
        )
        sync_course_to_sqlite_shadow(sql_db, course)
        section = create_section_doc(mongo_db, course_id=course.id, title="Module 1", description=None, order_index=1)
        sync_section_to_sqlite_shadow(sql_db, section)
        lesson = create_lesson_doc(
            mongo_db,
            course_id=course.id,
            section_id=section.id,
            title="Async Queues",
            content="Task queues decouple background processing from request handlers using brokers and workers.",
            video_url=None,
            order_index=1,
        )
        sync_lesson_to_sqlite_shadow(sql_db, lesson)
        enr = create_enrollment_doc(
            mongo_db,
            student_id=student.id,
            course_id=course.id,
            enrollment_status="approved",
        )
        sync_enrollment_to_sqlite_shadow(sql_db, enr)

        # Low-scoring failed quiz attempt exercises the fixed max_score -> percentage path
        quiz = create_quiz_doc(
            mongo_db,
            course_id=course.id,
            section_id=section.id,
            lesson_id=lesson.id,
            title="Queue Mastery Check",
            description=None,
            passing_score=70,
            is_published=True,
            time_limit_minutes=10,
            max_attempts=3,
        )
        sync_quiz_to_sqlite_shadow(sql_db, quiz)
        attempt = create_quiz_attempt_doc(
            mongo_db,
            quiz_id=quiz.id,
            student_id=student.id,
            attempt_number=1,
            score=40.0,
            total_points=10,
            passed=False,
            is_completed=True,
        )
        sync_quiz_attempt_to_sqlite_shadow(sql_db, attempt)
    finally:
        sql_db.close()

    # Chat persisted to MongoDB + SQLite shadow
    chat_res = client.post(
        "/api/v1/ai/chat",
        headers=student_headers,
        json={"message": "Explain task queues.", "course_id": course.id, "lesson_id": lesson.id},
    )
    assert chat_res.status_code == 200, chat_res.text
    conv_id = chat_res.json()["conversation_id"]

    assert mongo_db["ai_conversations"].find_one({"id": conv_id}) is not None
    assert mongo_db["ai_messages"].count_documents({"conversation_id": conv_id}) == 2

    check_db = SessionLocal()
    try:
        assert check_db.query(AIConversation).filter(AIConversation.id == conv_id).first() is not None
        assert check_db.query(AIMessage).filter(AIMessage.conversation_id == conv_id).count() == 2
    finally:
        check_db.close()

    # Study recommendations include review_quiz without AttributeError
    rec_res = client.get("/api/v1/ai/study-recommendations", headers=student_headers)
    assert rec_res.status_code == 200, rec_res.text
    types = {item["type"] for item in rec_res.json()["recommendations"]}
    assert "continue_lesson" in types
    assert "review_quiz" in types

    # Other student gets 403 on conversation detail and delete
    _, other_headers = _register_student(client)
    assert client.get(f"/api/v1/ai/conversations/{conv_id}", headers=other_headers).status_code == 403
    assert client.delete(f"/api/v1/ai/conversations/{conv_id}", headers=other_headers).status_code == 403

    # Owner deletes conversation from MongoDB and SQLite shadow
    del_res = client.delete(f"/api/v1/ai/conversations/{conv_id}", headers=student_headers)
    assert del_res.status_code == 200
    assert mongo_db["ai_conversations"].find_one({"id": conv_id}) is None
    assert mongo_db["ai_messages"].count_documents({"conversation_id": conv_id}) == 0

    # Rollback test if SQLite shadow fails during handle_ai_chat
    import app.services.ai_service as ai_service

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated shadow failure")

    monkeypatch.setattr(ai_service, "sync_ai_conversation_to_sqlite_shadow", _boom)
    before_convs = mongo_db["ai_conversations"].count_documents({})
    try:
        client.post(
            "/api/v1/ai/chat",
            headers=student_headers,
            json={"message": "Rollback test"},
        )
    except RuntimeError:
        pass
    assert mongo_db["ai_conversations"].count_documents({}) == before_convs


def test_phase3d_admin_stats_instructor_analytics_profile_and_student_dashboard(client):
    mongo_db = get_mongo_database()
    admin_headers = _login(client, "admin@eduverse.io")
    inst_headers = _login(client, "sarah.chen@eduverse.io")
    student_headers = _login(client, "alex.rivera@eduverse.io")

    # 1. Admin /stats matches MongoDB state
    stats_res = client.get("/api/v1/admin/stats", headers=admin_headers)
    assert stats_res.status_code == 200, stats_res.text
    stats = stats_res.json()
    assert stats["total_users"] == mongo_db["users"].count_documents({})
    assert stats["total_courses"] == mongo_db["courses"].count_documents({})
    assert stats["total_enrollments"] == mongo_db["course_enrollments"].count_documents({})
    assert client.get("/api/v1/admin/stats", headers=student_headers).status_code == 403

    # 2. Admin /analytics endpoints work with MongoDB & reject non-admin
    for path in ("dashboard", "overview", "students", "courses", "instructors", "trends", "activities"):
        res = client.get(f"/api/v1/admin/analytics/{path}", headers=admin_headers)
        assert res.status_code == 200, res.text
        assert client.get(f"/api/v1/admin/analytics/{path}", headers=inst_headers).status_code == 403

    # 3. Instructor /profile + /dashboard + course analytics/reports + ownership checks
    # Seeded instructor sarah.chen has no InstructorProfile row -> 404; instructor with profile -> 200
    assert client.get("/api/v1/instructor/profile", headers=inst_headers).status_code == 404
    assert client.get("/api/v1/instructor/profile", headers=student_headers).status_code == 403

    from app.repositories.user_repository import ensure_instructor_profile_for_user, get_user_by_email, update_user_fields
    from app.security.password import hash_password

    inst_email = f"inst-prof-{uuid4().hex[:8]}@eduverse.io"
    reg_inst = client.post(
        "/api/v1/admin/instructors",
        headers=admin_headers,
        json={
            "full_name": "Prof Phase3D",
            "email": inst_email,
            "phone_number": "9876543210",
            "qualification": "PhD",
            "department": "Computer Science",
            "subject_expertise": "Distributed Systems",
            "experience_years": 6,
        },
    )
    assert reg_inst.status_code == 201, reg_inst.text
    prof_user = get_user_by_email(mongo_db, inst_email)
    assert prof_user is not None
    update_user_fields(mongo_db, prof_user.id, {"password_hash": hash_password("StrongPassword123!")})
    prof_headers = _login(client, inst_email, "StrongPassword123!")
    profile_res = client.get("/api/v1/instructor/profile", headers=prof_headers)
    assert profile_res.status_code == 200, profile_res.text
    assert profile_res.json()["email"] == inst_email

    dash_res = client.get("/api/v1/instructor/dashboard", headers=inst_headers)
    assert dash_res.status_code == 200, dash_res.text
    courses_overview = dash_res.json()["courses_overview"]
    if courses_overview:
        cid = courses_overview[0]["course_id"]
        assert client.get(f"/api/v1/instructor/courses/{cid}/analytics", headers=inst_headers).status_code == 200
        report_res = client.get(f"/api/v1/instructor/courses/{cid}/student-report", headers=inst_headers)
        assert report_res.status_code == 200
        csv_res = client.get(f"/api/v1/instructor/courses/{cid}/student-report/csv", headers=inst_headers)
        assert csv_res.status_code == 200
        assert "Student Name" in csv_res.text

        # Non-owner student denied 403
        assert client.get(f"/api/v1/instructor/courses/{cid}/analytics", headers=student_headers).status_code == 403

    # 4. Student dashboard & tracking endpoints
    for path in ("/api/v1/student/dashboard", "/api/v1/student/my-learning", "/api/v1/student/assignments", "/api/v1/student/quiz-history", "/api/v1/student/recommendations"):
        s_res = client.get(path, headers=student_headers)
        assert s_res.status_code == 200, s_res.text
        assert client.get(path, headers=inst_headers).status_code == 403


def test_phase3d_ai_quiz_planner_and_instructor_ai_persistence(client, monkeypatch):
    import app.services.ai_quiz_service as ai_quiz_service
    import app.services.study_planner_service as planner_service

    mongo_db = get_mongo_database()
    sql_db = SessionLocal()
    try:
        email, student_headers = _register_student(client)
        student = get_user_by_email(mongo_db, email)
        instructor = get_user_by_email(mongo_db, "sarah.chen@eduverse.io")
        course = create_course_doc(
            mongo_db,
            title=f"Phase3D Persistence Course {uuid4().hex[:6]}",
            description="Course for persistence check.",
            category="Backend",
            difficulty="Beginner",
            instructor_id=instructor.id,
            is_published=True,
        )
        sync_course_to_sqlite_shadow(sql_db, course)
        sec = create_section_doc(mongo_db, course_id=course.id, title="Sec 1", description=None, order_index=1)
        sync_section_to_sqlite_shadow(sql_db, sec)
        les = create_lesson_doc(
            mongo_db,
            course_id=course.id,
            section_id=sec.id,
            title="Lesson One",
            content="Relational keys and document models both store entities cleanly.",
            video_url=None,
            order_index=1,
        )
        sync_lesson_to_sqlite_shadow(sql_db, les)
        enr = create_enrollment_doc(
            mongo_db,
            student_id=student.id,
            course_id=course.id,
            enrollment_status="approved",
        )
        sync_enrollment_to_sqlite_shadow(sql_db, enr)
    finally:
        sql_db.close()

    def fake_quiz(*args, **kwargs):
        return {
            "questions": [
                {
                    "question": f"True or false question {i}?",
                    "question_type": "true_false",
                    "options": [],
                    "correct_answer": "True",
                    "explanation": "Supported by lesson text.",
                    "difficulty": "easy",
                }
                for i in range(4)
            ]
            + [
                {
                    "question": "What stores entities cleanly?",
                    "question_type": "short_answer",
                    "options": [],
                    "correct_answer": "Document models",
                    "explanation": "Stated directly in lesson text.",
                    "difficulty": "easy",
                }
            ]
        }

    monkeypatch.setattr(ai_quiz_service, "request_structured_ai_json", fake_quiz)
    gen_res = client.post(
        "/api/v1/student/ai-learning/quizzes",
        headers=student_headers,
        json={
            "course_id": course.id,
            "lesson_id": les.id,
            "difficulty": "easy",
            "question_count": 5,
            "question_type": "mixed",
        },
    )
    assert gen_res.status_code == 201, gen_res.text
    quiz_id = gen_res.json()["quiz"]["id"]
    assert mongo_db["ai_quizzes"].find_one({"id": quiz_id}) is not None
    assert mongo_db["ai_quiz_questions"].count_documents({"quiz_id": quiz_id}) == 5

    # Study planner falls back to rule-based plan cleanly & writes Mongo + SQLite shadow
    from app.services.structured_ai import AIProviderNotConfigured

    monkeypatch.setattr(
        planner_service,
        "request_structured_ai_json",
        lambda *a, **k: (_ for _ in ()).throw(AIProviderNotConfigured("offline")),
    )
    plan_res = client.post(
        "/api/v1/student/ai-learning/planner/generate",
        headers=student_headers,
        json={
            "course_ids": [course.id],
            "available_hours_per_day": 2,
            "preferred_time": "evening",
            "time_zone": "UTC",
            "daily_duration_minutes": 45,
            "target_completion_date": (date.today() + timedelta(days=7)).isoformat(),
            "deadlines": [],
        },
    )
    assert plan_res.status_code == 201, plan_res.text
    plan_id = plan_res.json()["plan_id"]
    assert mongo_db["study_plans"].find_one({"id": plan_id}) is not None
    assert mongo_db["study_tasks"].count_documents({"plan_id": plan_id}) == 1

    check_db = SessionLocal()
    try:
        assert check_db.query(AIQuiz).filter(AIQuiz.id == quiz_id).first() is not None
        assert check_db.query(StudyPlan).filter(StudyPlan.id == plan_id).first() is not None
        assert check_db.query(StudyTask).filter(StudyTask.plan_id == plan_id).count() == 1
    finally:
        check_db.close()
