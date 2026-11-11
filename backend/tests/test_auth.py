import pytest
from app.models.user import User


def test_student_registration(client):
    payload = {
        "email": "new.student@eduverse.io",
        "full_name": "Test Student",
        "password": "SecurePassword123!",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new.student@eduverse.io"
    assert data["role"] == "student"


def test_registration_duplicate_email(client):
    payload = {
        "email": "new.student@eduverse.io",
        "full_name": "Duplicate Student",
        "password": "SecurePassword123!",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


def test_registration_role_escalation_prevented(client):
    # Public registration must reject administrator accounts.
    payload = {
        "email": "hacker@eduverse.io",
        "full_name": "Escalation Attempt",
        "password": "SecurePassword123!",
        "role": "admin",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Self-registration as Administrator is not permitted."


def test_login_success(client):
    payload = {
        "email": "new.student@eduverse.io",
        "password": "SecurePassword123!",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "new.student@eduverse.io"


def test_login_invalid_password(client):
    payload = {
        "email": "new.student@eduverse.io",
        "password": "WrongPassword999!",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401


def test_demo_account_strict_password_verification(client):
    # Legitimate demo login with exact password succeeds
    valid_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "sarah.chen@eduverse.io", "password": "EduVerseDemo2026!"},
    )
    assert valid_resp.status_code == 200

    # Omitting trailing exclamation mark must strictly fail with 401
    invalid_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "sarah.chen@eduverse.io", "password": "EduVerseDemo2026"},
    )
    assert invalid_resp.status_code == 401
    assert "Invalid email or password" in invalid_resp.json()["detail"]


@pytest.mark.parametrize(
    ("email", "submitted_role", "expected_role"),
    [
        ("alex.rivera@eduverse.io", "admin", "student"),
        ("sarah.chen@eduverse.io", "student", "instructor"),
        ("admin@eduverse.io", "student", "admin"),
    ],
)
def test_login_uses_database_role(client, email, submitted_role, expected_role):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "EduVerseDemo2026!",
            "role": submitted_role,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["role"] == expected_role
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


def test_login_unknown_email_returns_generic_error(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "not.registered@eduverse.io", "password": "AnyPassword123!"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_student_cannot_access_instructor_dashboard_api(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "alex.rivera@eduverse.io", "password": "EduVerseDemo2026!"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/instructor/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_instructor_cannot_access_student_dashboard_api(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "sarah.chen@eduverse.io", "password": "EduVerseDemo2026!"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/student/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("remember_me", "cookie_has_max_age"),
    [(True, True), (False, False)],
)
def test_remember_me_controls_cookie_persistence(client, remember_me, cookie_has_max_age):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "alex.rivera@eduverse.io",
            "password": "EduVerseDemo2026!",
            "remember_me": remember_me,
        },
    )

    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert ("max-age=" in cookie) is cookie_has_max_age


def test_login_cors_allows_ipv6_frontend_origin(client):
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://[::1]:4200",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://[::1]:4200"
