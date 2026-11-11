from uuid import uuid4

import pytest
import smtplib

from app.database import SessionLocal
from app.models.email_delivery import EmailDelivery
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson
from app.routers import courses as courses_router
from app.routers import instructor as instructor_router
from app.services import email_service


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

    notified = []

    def record_notification(db, delivery, settings):
        notified.append(delivery.recipient_email)
        return "sent"

    monkeypatch.setattr(courses_router, "send_email_delivery", record_notification)

    course_detail = client.get("/api/v1/courses/2").json()
    # Enroll in course 2
    enroll_resp = client.post("/api/v1/courses/2/enroll", headers=headers)
    assert enroll_resp.status_code == 201
    enrollment = enroll_resp.json()
    assert enrollment["status"] == "pending"
    assert enrollment["student_email"] == "new.student@eduverse.io"
    assert enrollment["course_name"]
    assert enrollment["instructor_id"]
    assert enrollment["email_notification_status"] == "sent"
    assert notified == [course_detail["instructor"]["email"]]

    # Attempt duplicate enrollment -> should return 409
    dup_resp = client.post("/api/v1/courses/2/enroll", headers=headers)
    assert dup_resp.status_code == 409
    assert notified == [course_detail["instructor"]["email"]]
    approve = client.post(
        f"/api/v1/instructor/enrollments/{enrollment['id']}/approve",
        headers=_login_as(client, "sarah.chen@eduverse.io"),
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"


@pytest.mark.parametrize(
    "smtp_error",
    [
        smtplib.SMTPAuthenticationError(535, b"authentication failed"),
        TimeoutError("SMTP connection timed out"),
    ],
)
def test_enrollment_is_saved_when_email_delivery_fails(client, monkeypatch, smtp_error):
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

    attempts = []

    for key, value in {
        "EMAIL_HOST_USER": "mailer@example.com",
        "EMAIL_HOST_PASSWORD": "fake-app-password",
        "DEFAULT_FROM_EMAIL": "mailer@example.com",
        "EMAIL_USE_TLS": True,
    }.items():
        monkeypatch.setattr(courses_router.settings, key, value)

    def fail_notification(message, settings):
        attempts.append(message["To"])
        raise smtp_error

    monkeypatch.setattr(email_service, "_send_smtp_message", fail_notification)
    enroll = client.post("/api/v1/courses/1/enroll", headers=headers)

    assert enroll.status_code == 201
    assert enroll.json()["email_notification_status"] == "failed"
    assert enroll.json()["status"] == "pending"
    duplicate = client.post("/api/v1/courses/1/enroll", headers=headers)
    assert duplicate.status_code == 409
    assert attempts == ["sarah.chen@eduverse.io"]
    with SessionLocal() as db:
        delivery = (
            db.query(EmailDelivery)
            .filter(EmailDelivery.enrollment_id == enroll.json()["id"])
            .one()
        )
        assert delivery.status == "failed"
        assert delivery.attempts == 1
        assert delivery.last_error == type(smtp_error).__name__

    monkeypatch.setattr(email_service, "_send_smtp_message", lambda message, settings: None)
    retry = client.post(
        f"/api/v1/admin/email/deliveries/{delivery.id}/retry",
        headers=_login_as(client, "admin@eduverse.io"),
    )
    assert retry.status_code == 200
    with SessionLocal() as db:
        delivery = db.query(EmailDelivery).filter_by(id=delivery.id).one()
        assert delivery.status == "sent"
        assert delivery.attempts == 2
    assert client.post(
        f"/api/v1/admin/email/deliveries/{delivery.id}/retry",
        headers=_login_as(client, "admin@eduverse.io"),
    ).status_code == 409
    my_courses = client.get("/api/v1/enrollments/my-courses", headers=headers)
    assert my_courses.status_code == 200
    assert any(
        item["course_id"] == 1 and item["status"] == "pending"
        for item in my_courses.json()
    )


def test_missing_smtp_credentials_keep_request_and_allow_retry(client, monkeypatch):
    _, headers = _register_and_login_student(client)
    for key in ("EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD", "DEFAULT_FROM_EMAIL"):
        monkeypatch.setattr(courses_router.settings, key, "")

    response = client.post("/api/v1/courses/1/enroll", headers=headers)
    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert response.json()["email_notification_status"] == "not_configured"

    with SessionLocal() as db:
        delivery = db.query(EmailDelivery).filter_by(
            id=response.json()["email_delivery_id"]
        ).one()
        assert delivery.status == "failed"
        assert delivery.last_error == "EmailNotConfiguredError"
        assert delivery.attempts == 1


def test_enrollment_and_roster_require_expected_roles(client, monkeypatch):
    monkeypatch.setattr(courses_router, "send_email_delivery", lambda *args: "sent")
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
    course_three_enrollment = client.post(
        "/api/v1/courses/3/enroll",
        headers=student_headers,
    )
    assert course_three_enrollment.status_code == 201
    approve_course_three = client.post(
        f"/api/v1/instructor/enrollments/{course_three_enrollment.json()['id']}/approve",
        headers=_login_as(client, "marcus.vance@eduverse.io"),
    )
    assert approve_course_three.status_code == 200

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


def _register_and_login_student(client):
    email = f"approval-{uuid4().hex}@eduverse.io"
    password = "SecurePassword123!"
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Approval Test Student", "password": password},
    )
    assert registered.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    return email, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _login_as(client, email):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "EduVerseDemo2026!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_instructor_approval_grants_access_and_notifies_student(client, monkeypatch):
    with SessionLocal() as db:
        lesson_id = db.query(Lesson.id).filter(Lesson.course_id == 1).first()[0]
    student_email, student_headers = _register_and_login_student(client)
    deliveries = []

    def record_delivery(db, delivery, settings):
        deliveries.append((delivery.event_type, delivery.recipient_email))
        return "sent"

    monkeypatch.setattr(courses_router, "send_email_delivery", record_delivery)
    monkeypatch.setattr(instructor_router, "send_email_delivery", record_delivery)
    enrollment_response = client.post(
        "/api/v1/courses/1/enroll",
        headers=student_headers,
    )
    assert enrollment_response.status_code == 201
    enrollment_id = enrollment_response.json()["id"]
    assert enrollment_response.json()["status"] == "pending"
    assert deliveries == [("enrollment_request", "sarah.chen@eduverse.io")]
    assert client.get(f"/api/v1/lessons/{lesson_id}", headers=student_headers).status_code == 403
    assert client.get(
        "/api/v1/materials/course/1",
        headers=student_headers,
    ).status_code == 403
    pending_dashboard = client.get("/api/v1/student/dashboard", headers=student_headers)
    assert any(
        item["enrollment_status"] == "pending"
        for item in pending_dashboard.json()["enrolled_courses"]
    )

    instructor_headers = _login_as(client, "sarah.chen@eduverse.io")
    other_instructor_headers = _login_as(client, "marcus.vance@eduverse.io")
    request_list = client.get("/api/v1/instructor/enrollment-requests", headers=instructor_headers)
    assert request_list.status_code == 200
    assert any(item["enrollment_id"] == enrollment_id for item in request_list.json())

    assert client.get(
        "/api/v1/instructor/enrollment-requests",
        headers=other_instructor_headers,
    ).json() == []
    assert client.post(
        f"/api/v1/instructor/enrollments/{enrollment_id}/approve",
        headers=other_instructor_headers,
    ).status_code == 403
    assert client.post(
        f"/api/v1/instructor/enrollments/{enrollment_id}/approve",
        headers=student_headers,
    ).status_code == 403
    assert client.post(
        f"/api/v1/instructor/enrollments/{enrollment_id}/approve",
        headers=_login_as(client, "admin@eduverse.io"),
    ).status_code == 403

    approved = client.post(
        f"/api/v1/instructor/enrollments/{enrollment_id}/approve",
        headers=instructor_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["email_notification_status"] == "sent"
    assert deliveries[-1] == ("enrollment_approved", student_email)
    assert client.post(
        f"/api/v1/instructor/enrollments/{enrollment_id}/approve",
        headers=instructor_headers,
    ).status_code == 409
    assert client.get(f"/api/v1/lessons/{lesson_id}", headers=student_headers).status_code == 200
    assert client.get(
        "/api/v1/materials/course/1",
        headers=student_headers,
    ).status_code == 200
    my_learning = client.get("/api/v1/student/my-learning", headers=student_headers)
    assert any(
        item["enrollment_status"] == "approved"
        for item in my_learning.json()
    )


def test_instructor_rejection_preserves_request_and_denies_access(client, monkeypatch):
    with SessionLocal() as db:
        lesson_id = db.query(Lesson.id).filter(Lesson.course_id == 1).first()[0]
    student_email, student_headers = _register_and_login_student(client)
    notifications = []
    monkeypatch.setattr(
        courses_router,
        "send_email_delivery",
        lambda db, delivery, settings: "sent",
    )
    monkeypatch.setattr(
        instructor_router,
        "send_email_delivery",
        lambda db, delivery, settings: notifications.append(
            (delivery.event_type, delivery.recipient_email)
        ) or "sent",
    )
    enrolled = client.post("/api/v1/courses/1/enroll", headers=student_headers)
    assert enrolled.status_code == 201
    enrollment_id = enrolled.json()["id"]

    rejected = client.post(
        f"/api/v1/instructor/enrollments/{enrollment_id}/reject",
        headers=_login_as(client, "sarah.chen@eduverse.io"),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert notifications == [("enrollment_rejected", student_email)]
    assert client.get(f"/api/v1/lessons/{lesson_id}", headers=student_headers).status_code == 403
    assert client.get(
        "/api/v1/materials/course/1",
        headers=student_headers,
    ).status_code == 403

    with SessionLocal() as db:
        enrollment = db.query(CourseEnrollment).filter_by(id=enrollment_id).one()
        assert enrollment.status == "rejected"
        assert enrollment.reviewed_at is not None
        assert enrollment.reviewed_by_instructor_id is not None

    my_courses = client.get("/api/v1/enrollments/my-courses", headers=student_headers)
    assert any(item["id"] == enrollment_id and item["status"] == "rejected" for item in my_courses.json())
    assert client.post("/api/v1/courses/1/enroll", headers=student_headers).status_code == 409


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
