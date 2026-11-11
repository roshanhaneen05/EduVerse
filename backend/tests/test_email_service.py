from datetime import datetime, timezone
import smtplib
import ssl
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.user import User
from app.routers import admin as admin_router
from app.services.email_service import (
    EmailNotConfiguredError,
    InvalidEmailAddressError,
    build_approval_email,
    build_enrollment_email,
    build_rejection_email,
    send_enrollment_email,
)


def test_enrollment_email_contains_required_details():
    student = User(
        full_name="Test Student",
        email="student@example.com",
        password_hash="not-used",
        role="student",
    )
    instructor = User(
        full_name="Test Instructor",
        email="instructor@example.com",
        password_hash="not-used",
        role="instructor",
    )
    course = Course(
        title="Example Course",
        description="Course description",
        category="Testing",
        instructor_id=1,
        is_published=True,
    )
    enrollment = CourseEnrollment(
        student_id=1,
        course_id=1,
        enrolled_at=datetime(2026, 3, 19, tzinfo=timezone.utc),
        status="pending",
    )
    settings = Settings(
        EMAIL_HOST="smtp.gmail.com",
        EMAIL_PORT=587,
        EMAIL_HOST_USER="mailer@example.com",
        EMAIL_HOST_PASSWORD="app-password",
        DEFAULT_FROM_EMAIL="no-reply@example.com",
        EMAIL_USE_TLS=True,
    )

    message = build_enrollment_email(enrollment, student, course, instructor, settings)

    assert message["To"] == instructor.email
    assert message["Subject"] == "New Course Enrollment Request - EduVerse"
    plain_body, html_part = message.get_payload()
    body = plain_body.get_content()
    assert student.full_name in body
    assert student.email in body
    assert course.title in body
    assert "Enrollment date:" in body
    html_body = html_part.get_content()
    assert "EduVerse" in html_body
    assert student.full_name in html_body
    assert student.email in html_body
    assert course.title in html_body
    assert "Request status" in html_body
    assert "Pending" in body


def test_enrollment_email_escapes_untrusted_html_content():
    student = SimpleNamespace(full_name="<Student>", email="student@example.com")
    instructor = SimpleNamespace(full_name="<Instructor>", email="instructor@example.com")
    course = SimpleNamespace(title="<Course>")
    enrollment = SimpleNamespace(enrolled_at=datetime(2026, 3, 19, tzinfo=timezone.utc))
    settings = Settings(
        EMAIL_HOST_USER="mailer@example.com",
        EMAIL_HOST_PASSWORD="app-password",
        DEFAULT_FROM_EMAIL="mailer@example.com",
    )

    message = build_enrollment_email(enrollment, student, course, instructor, settings)
    html_body = message.get_payload()[1].get_content()

    assert "&lt;Student&gt;" in html_body
    assert "&lt;Instructor&gt;" in html_body
    assert "&lt;Course&gt;" in html_body
    assert "<Student>" not in html_body


@pytest.mark.parametrize(
    ("builder", "subject", "required_text"),
    [
        (build_approval_email, "Your Enrollment Has Been Approved - EduVerse", "can now sign in"),
        (build_rejection_email, "Your Course Enrollment Request - EduVerse", "not approved"),
    ],
)
def test_student_decision_emails_use_the_registered_student_email(builder, subject, required_text):
    student = SimpleNamespace(full_name="Student", email="student@example.com")
    instructor = SimpleNamespace(full_name="Instructor", email="instructor@example.com")
    course = SimpleNamespace(title="Example Course")
    enrollment = SimpleNamespace(enrolled_at=datetime(2026, 3, 19, tzinfo=timezone.utc))
    settings = Settings(
        EMAIL_HOST_USER="mailer@example.com",
        EMAIL_HOST_PASSWORD="app-password",
        DEFAULT_FROM_EMAIL="mailer@example.com",
    )

    message = builder(enrollment, student, course, instructor, settings)

    assert message["To"] == student.email
    assert message["Subject"] == subject
    assert required_text in message.get_payload()[0].get_content()
    assert course.title in message.get_payload()[1].get_content()


def test_enrollment_email_requires_smtp_configuration():
    with pytest.raises(EmailNotConfiguredError):
        build_enrollment_email(
            CourseEnrollment(
                student_id=1,
                course_id=1,
                enrolled_at=datetime.now(timezone.utc),
                status="pending",
            ),
            SimpleNamespace(full_name="Student", email="student@example.com"),
            SimpleNamespace(title="Course"),
            SimpleNamespace(full_name="Instructor", email="instructor@example.com"),
            Settings(EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="", DEFAULT_FROM_EMAIL=""),
        )


def test_enrollment_email_rejects_invalid_instructor_email():
    with pytest.raises(InvalidEmailAddressError, match="Instructor email"):
        build_enrollment_email(
            CourseEnrollment(
                student_id=1,
                course_id=1,
                enrolled_at=datetime.now(timezone.utc),
                status="pending",
            ),
            SimpleNamespace(full_name="Student", email="student@example.com"),
            SimpleNamespace(title="Course"),
            SimpleNamespace(full_name="Instructor", email="not-an-email"),
            Settings(
                EMAIL_HOST_USER="mailer@example.com",
                EMAIL_HOST_PASSWORD="app-password",
                DEFAULT_FROM_EMAIL="no-reply@example.com",
            ),
        )


def test_sending_uses_gmail_starttls_and_app_password(monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ehlo(self):
            calls.append(("ehlo",))

        def starttls(self, context):
            assert isinstance(context, ssl.SSLContext)
            calls.append(("starttls",))

        def login(self, username, password):
            calls.append(("login", username, password))

        def send_message(self, message):
            calls.append(("send", message["To"]))
            return {}

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    student = SimpleNamespace(full_name="Student", email="student@example.com")
    instructor = SimpleNamespace(full_name="Instructor", email="instructor@example.com")
    course = SimpleNamespace(title="Course")
    enrollment = SimpleNamespace(enrolled_at=datetime.now(timezone.utc))
    settings = Settings(
        EMAIL_HOST="smtp.gmail.com",
        EMAIL_PORT=587,
        EMAIL_HOST_USER="mailer@example.com",
        EMAIL_HOST_PASSWORD="app-password",
        DEFAULT_FROM_EMAIL="mailer@example.com",
        EMAIL_USE_TLS=True,
    )

    send_enrollment_email(enrollment, student, course, instructor, settings)

    assert calls[0][:3] == ("connect", "smtp.gmail.com", 587)
    assert ("starttls",) in calls
    assert ("login", "mailer@example.com", "app-password") in calls
    assert ("send", "instructor@example.com") in calls


def test_legacy_smtp_environment_names_remain_supported():
    settings = Settings(
        SMTP_HOST="smtp.legacy.test",
        SMTP_PORT=2525,
        SMTP_USERNAME="legacy-user",
        SMTP_PASSWORD="legacy-password",
        SMTP_FROM_EMAIL="legacy@example.com",
        SMTP_STARTTLS=True,
    )

    assert settings.EMAIL_HOST == "smtp.legacy.test"
    assert settings.EMAIL_PORT == 2525
    assert settings.EMAIL_HOST_USER == "legacy-user"
    assert settings.EMAIL_HOST_PASSWORD == "legacy-password"
    assert settings.DEFAULT_FROM_EMAIL == "legacy@example.com"


def test_email_environment_variable_names_are_loaded(monkeypatch):
    monkeypatch.setenv("EMAIL_HOST", "smtp.gmail.com")
    monkeypatch.setenv("EMAIL_PORT", "587")
    monkeypatch.setenv("EMAIL_USE_TLS", "true")
    monkeypatch.setenv("EMAIL_HOST_USER", "mailer@example.com")
    monkeypatch.setenv("EMAIL_HOST_PASSWORD", "configured-app-password")
    monkeypatch.setenv("DEFAULT_FROM_EMAIL", "mailer@example.com")

    settings = Settings(_env_file=None)

    assert settings.EMAIL_HOST == "smtp.gmail.com"
    assert settings.EMAIL_PORT == 587
    assert settings.EMAIL_USE_TLS is True
    assert settings.EMAIL_HOST_USER == "mailer@example.com"
    assert settings.EMAIL_HOST_PASSWORD == "configured-app-password"
    assert settings.DEFAULT_FROM_EMAIL == "mailer@example.com"


def test_development_email_test_endpoint_sends_only_for_admin(client, monkeypatch):
    sent = []
    monkeypatch.setattr(admin_router.settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(
        admin_router,
        "send_test_email",
        lambda recipient, settings: sent.append(recipient),
    )

    student_login = client.post(
        "/api/v1/auth/login",
        json={"email": "alex.rivera@eduverse.io", "password": "EduVerseDemo2026!"},
    )
    student_headers = {
        "Authorization": f"Bearer {student_login.json()['access_token']}"
    }
    forbidden = client.post(
        "/api/v1/admin/email/test",
        json={"recipient_email": "test@example.com"},
        headers=student_headers,
    )
    assert forbidden.status_code == 403
    assert sent == []

    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@eduverse.io", "password": "EduVerseDemo2026!"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    response = client.post(
        "/api/v1/admin/email/test",
        json={"recipient_email": "test@example.com"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json() == {"message": "SMTP accepted the test email for delivery.", "detail": None}
    assert sent == ["test@example.com"]
    assert "password" not in response.text.lower()


def test_development_email_test_endpoint_reports_smtp_auth_failure(client, monkeypatch):
    monkeypatch.setattr(admin_router.settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(
        admin_router,
        "send_test_email",
        lambda *args: (_ for _ in ()).throw(
            smtplib.SMTPAuthenticationError(535, b"authentication failed")
        ),
    )
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@eduverse.io", "password": "EduVerseDemo2026!"},
    )
    response = client.post(
        "/api/v1/admin/email/test",
        json={"recipient_email": "test@example.com"},
        headers={"Authorization": f"Bearer {admin_login.json()['access_token']}"},
    )

    assert response.status_code == 502
    assert "Google App Password" in response.json()["detail"]
    assert response.json()["detail"] == (
        "SMTP authentication failed. Verify EMAIL_HOST_USER and the Google App Password."
    )


def test_email_test_endpoint_disabled_outside_development(client, monkeypatch):
    monkeypatch.setattr(admin_router.settings, "ENVIRONMENT", "production")
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@eduverse.io", "password": "EduVerseDemo2026!"},
    )
    response = client.post(
        "/api/v1/admin/email/test",
        json={"recipient_email": "test@example.com"},
        headers={"Authorization": f"Bearer {admin_login.json()['access_token']}"},
    )

    assert response.status_code == 404


def test_development_email_test_endpoint_reports_missing_configuration(client, monkeypatch):
    monkeypatch.setattr(admin_router.settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(admin_router.settings, "EMAIL_HOST_USER", "")
    monkeypatch.setattr(admin_router.settings, "EMAIL_HOST_PASSWORD", "")
    monkeypatch.setattr(admin_router.settings, "DEFAULT_FROM_EMAIL", "")
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@eduverse.io", "password": "EduVerseDemo2026!"},
    )
    response = client.post(
        "/api/v1/admin/email/test",
        json={"recipient_email": "test@example.com"},
        headers={"Authorization": f"Bearer {admin_login.json()['access_token']}"},
    )

    assert response.status_code == 503
    assert "EMAIL_HOST_USER" in response.json()["detail"]
    assert response.json()["detail"] == (
        "EMAIL_HOST_USER and EMAIL_HOST_PASSWORD must be configured."
    )


def test_development_cors_allows_configured_frontend_port(client):
    response = client.options(
        "/api/v1/courses/1/enroll",
        headers={
            "Origin": "http://localhost:55806",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:55806"
