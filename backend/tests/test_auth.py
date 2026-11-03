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
    # Attempting to register as 'admin' must still assign 'student'
    payload = {
        "email": "hacker@eduverse.io",
        "full_name": "Escalation Attempt",
        "password": "SecurePassword123!",
        "role": "admin",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "student"  # Strictly forced to student


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

