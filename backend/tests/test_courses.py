import smtplib
from uuid import uuid4

from app.routers import courses as courses_router


def _get_test_student_token(client):
    payload = {
        "email": "new.student@eduverse.io",
        "password": "SecurePassword123!",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    if response.status_code != 200:
        registration = client.post(
            "/api/v1/auth/register",
            json={**payload, "full_name": "New Student"},
        )
        assert registration.status_code in (201, 409)
        response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    return response.json()["access_token"]


def test_list_published_courses(client):
    response = client.get("/api/v1/courses")
    assert response.status_code == 200
    courses = response.json()
    assert isinstance(courses, list)
    assert len(courses) >= 1
    assert any("FastAPI" in c["title"] for c in courses)


def test_course_detail_and_outline(client):
    response = client.get("/api/v1/courses/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert "lessons" in data
    assert len(data["lessons"]) >= 1


def test_enrollment_and_duplicate_prevention(client, monkeypatch):
    token = _get_test_student_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    notified = {}

    def record_notification(enrollment, student, course, instructor, settings):
        notified["instructor_email"] = instructor.email

    monkeypatch.setattr(courses_router, "send_enrollment_email", record_notification)

    course_detail = client.get("/api/v1/courses/2").json()
    # Enroll in course 2
    enroll_resp = client.post("/api/v1/courses/2/enroll", headers=headers)
    assert enroll_resp.status_code == 201
    enrollment = enroll_resp.json()
    assert enrollment["status"] == "active"
    assert enrollment["student_email"] == "new.student@eduverse.io"
    assert enrollment["course_name"]
    assert enrollment["instructor_id"]
    assert enrollment["email_notification_status"] == "sent"
    assert notified["instructor_email"] == course_detail["instructor"]["email"]

    # Attempt duplicate enrollment -> should return 409
    dup_resp = client.post("/api/v1/courses/2/enroll", headers=headers)
    assert dup_resp.status_code == 409


def test_enrollment_is_saved_when_email_delivery_fails(client, monkeypatch):
    email = f"enrollment-{uuid4().hex}@eduverse.io"
    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Enrollment Test Student",
            "password": "SecurePassword123!",
        },
    )
    assert register.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def fail_notification(*args):
        raise smtplib.SMTPException("SMTP delivery failed")

    monkeypatch.setattr(courses_router, "send_enrollment_email", fail_notification)
    enroll = client.post("/api/v1/courses/1/enroll", headers=headers)

    assert enroll.status_code == 201
    assert enroll.json()["email_notification_status"] == "failed"
    my_courses = client.get("/api/v1/enrollments/my-courses", headers=headers)
    assert my_courses.status_code == 200
    assert any(item["course_id"] == 1 for item in my_courses.json())


def test_enrollment_and_roster_require_expected_roles(client, monkeypatch):
    monkeypatch.setattr(courses_router, "send_enrollment_email", lambda *args: None)
    instructor_login = client.post(
        "/api/v1/auth/login",
        json={"email": "sarah.chen@eduverse.io", "password": "EduVerseDemo2026!"},
    )
    instructor_headers = {
        "Authorization": f"Bearer {instructor_login.json()['access_token']}"
    }

    assert client.post("/api/v1/courses/1/enroll", headers=instructor_headers).status_code == 403

    student_headers = {"Authorization": f"Bearer {_get_test_student_token(client)}"}
    assert client.get("/api/v1/instructor/enrollments", headers=student_headers).status_code == 403
    assert client.post("/api/v1/courses/3/enroll", headers=student_headers).status_code == 201

    roster = client.get("/api/v1/instructor/enrollments", headers=instructor_headers)
    assert roster.status_code == 200
    assert roster.json()
    assert all(item["instructor_id"] == instructor_login.json()["user"]["id"] for item in roster.json())
    assert all(item["course_id"] != 3 for item in roster.json())

    other_instructor_login = client.post(
        "/api/v1/auth/login",
        json={"email": "marcus.vance@eduverse.io", "password": "EduVerseDemo2026!"},
    )
    other_roster = client.get(
        "/api/v1/instructor/enrollments",
        headers={"Authorization": f"Bearer {other_instructor_login.json()['access_token']}"},
    )
    assert other_roster.status_code == 200
    assert any(item["course_id"] == 3 for item in other_roster.json())


def test_lesson_completion_and_progress_recalculation(client):
    token = _get_test_student_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Get course 2 lessons
    course_detail = client.get("/api/v1/courses/2", headers=headers).json()
    first_lesson_id = course_detail["lessons"][0]["id"]

    # View lesson
    lesson_resp = client.get(f"/api/v1/lessons/{first_lesson_id}", headers=headers)
    assert lesson_resp.status_code == 200

    # Mark lesson completed
    comp_resp = client.post(f"/api/v1/lessons/{first_lesson_id}/complete", headers=headers)
    assert comp_resp.status_code == 200
    data = comp_resp.json()
    assert data["is_completed"] is True
    assert data["course_progress_percentage"] > 0
