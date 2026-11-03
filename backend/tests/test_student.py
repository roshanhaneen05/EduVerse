import pytest


def get_token(client, email: str, password: str = "EduVerseDemo2026!") -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.status_code}"
    return res.json()["access_token"]


def test_student_endpoints_require_authentication(client):
    client.cookies.clear()
    endpoints = [
        "/api/v1/student/dashboard",
        "/api/v1/student/my-learning",
        "/api/v1/student/courses/1/continue",
        "/api/v1/student/assignments",
        "/api/v1/student/quiz-history",
        "/api/v1/student/recommendations",
    ]
    for ep in endpoints:
        res = client.get(ep)
        assert res.status_code == 401, f"Expected 401 for unauthenticated request to {ep}"


def test_student_dashboard_metrics_and_telemetry(client):
    token = get_token(client, "alex.rivera@eduverse.io")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/student/dashboard", headers=headers)
    assert res.status_code == 200
    data = res.json()

    # Stats validation
    assert "stats" in data
    stats = data["stats"]
    assert stats["enrolled_courses_count"] >= 1
    assert stats["in_progress_courses_count"] >= 0
    assert stats["completed_courses_count"] >= 0
    assert 0.0 <= stats["overall_progress_percentage"] <= 100.0
    assert stats["total_quizzes_taken"] >= 0

    # Lists validation
    assert "recently_accessed_lessons" in data
    assert isinstance(data["recently_accessed_lessons"], list)
    assert "upcoming_deadlines" in data
    assert isinstance(data["upcoming_deadlines"], list)
    assert "recent_grades" in data
    assert isinstance(data["recent_grades"], list)
    assert "recommended_courses" in data
    assert isinstance(data["recommended_courses"], list)
    assert "enrolled_courses" in data
    assert len(data["enrolled_courses"]) == stats["enrolled_courses_count"]

    # Verify enrolled courses structure
    for c in data["enrolled_courses"]:
        assert "course_id" in c
        assert "course_title" in c
        assert "completion_percentage" in c
        assert "total_lessons" in c
        assert "completed_lessons" in c
        assert "remaining_lessons" in c
        assert c["total_lessons"] >= c["completed_lessons"]


def test_student_my_learning_and_filters(client):
    token = get_token(client, "alex.rivera@eduverse.io")
    headers = {"Authorization": f"Bearer {token}"}

    # All courses
    res_all = client.get("/api/v1/student/my-learning", headers=headers)
    assert res_all.status_code == 200
    courses = res_all.json()
    assert isinstance(courses, list)
    assert len(courses) >= 1

    for c in courses:
        assert "enrollment_id" in c
        assert "course_id" in c
        assert "course_title" in c
        assert "status" in c
        assert c["status"] in ("in_progress", "completed")
        assert "next_lesson_id" in c

    # Filter in_progress
    res_prog = client.get("/api/v1/student/my-learning?status=in_progress", headers=headers)
    assert res_prog.status_code == 200
    for c in res_prog.json():
        assert c["status"] == "in_progress"

    # Filter completed
    res_comp = client.get("/api/v1/student/my-learning?status=completed", headers=headers)
    assert res_comp.status_code == 200
    for c in res_comp.json():
        assert c["status"] == "completed"


def test_continue_learning_action(client):
    token = get_token(client, "alex.rivera@eduverse.io")
    headers = {"Authorization": f"Bearer {token}"}

    # Get an enrolled course ID
    my_learning = client.get("/api/v1/student/my-learning", headers=headers).json()
    assert len(my_learning) >= 1
    course_id = my_learning[0]["course_id"]

    # Continue learning for enrolled course
    res = client.get(f"/api/v1/student/courses/{course_id}/continue", headers=headers)
    assert res.status_code == 200
    cont = res.json()
    assert cont["course_id"] == course_id
    assert "next_lesson_id" in cont
    assert "reason" in cont
    assert cont["reason"] in (
        "latest_progress",
        "first_incomplete",
        "course_completed_first_lesson",
        "no_lessons",
    )

    # Continue learning for non-enrolled course -> 403 Forbidden
    unauthorized_res = client.get("/api/v1/student/courses/999999/continue", headers=headers)
    assert unauthorized_res.status_code == 403


def test_student_assignments_tracking_and_privacy(client):
    token = get_token(client, "alex.rivera@eduverse.io")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/student/assignments", headers=headers)
    assert res.status_code == 200
    assignments = res.json()
    assert isinstance(assignments, list)

    for a in assignments:
        assert "assignment_id" in a
        assert "assignment_title" in a
        assert "max_marks" in a
        assert "submission_status" in a
        assert a["submission_status"] in ("not_submitted", "submitted", "graded", "past_due")

    # Filter pending
    res_pending = client.get("/api/v1/student/assignments?filter=pending", headers=headers)
    assert res_pending.status_code == 200
    for a in res_pending.json():
        assert a["submission_status"] == "not_submitted"


def test_student_quiz_history_and_privacy(client):
    token = get_token(client, "alex.rivera@eduverse.io")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/student/quiz-history", headers=headers)
    assert res.status_code == 200
    attempts = res.json()
    assert isinstance(attempts, list)

    for a in attempts:
        assert "attempt_id" in a
        assert "quiz_id" in a
        assert "quiz_title" in a
        assert "score" in a
        assert "passing_score" in a
        assert "passed" in a
        # Crucial security check: answer keys must never be in quiz attempt summaries
        assert "questions" not in a
        assert "answers" not in a
        assert "answer_key" not in a


def test_course_recommendations_excludes_enrolled(client):
    token = get_token(client, "alex.rivera@eduverse.io")
    headers = {"Authorization": f"Bearer {token}"}

    # Get enrolled course IDs
    my_learning = client.get("/api/v1/student/my-learning", headers=headers).json()
    enrolled_ids = {c["course_id"] for c in my_learning}

    res = client.get("/api/v1/student/recommendations?limit=4", headers=headers)
    assert res.status_code == 200
    recommendations = res.json()
    assert isinstance(recommendations, list)

    for rec in recommendations:
        assert rec["id"] not in enrolled_ids, f"Recommended course {rec['id']} is already enrolled!"
        assert rec["is_published"] is True


def test_empty_student_account_handling(client):
    # Register brand new student with 0 enrollments
    new_email = "brand.new.student@eduverse.io"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": new_email,
            "password": "EduVerseDemo2026!",
            "full_name": "Brand New Student",
        },
    )

    token = get_token(client, new_email)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/student/dashboard", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["stats"]["enrolled_courses_count"] == 0
    assert data["stats"]["overall_progress_percentage"] == 0.0
    assert data["stats"]["total_quizzes_taken"] == 0
    assert len(data["enrolled_courses"]) == 0
    assert len(data["recently_accessed_lessons"]) == 0

    res_my_learn = client.get("/api/v1/student/my-learning", headers=headers)
    assert res_my_learn.status_code == 200
    assert res_my_learn.json() == []

    res_assign = client.get("/api/v1/student/assignments", headers=headers)
    assert res_assign.status_code == 200
    assert res_assign.json() == []

    res_quiz = client.get("/api/v1/student/quiz-history", headers=headers)
    assert res_quiz.status_code == 200
    assert res_quiz.json() == []
