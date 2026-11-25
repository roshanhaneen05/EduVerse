from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.mongo_schema import COUNTERS_COLLECTION, next_sequence_id
from app.mongodb import get_mongo_database
from app.repositories.user_repository import get_user_by_email
from app.security.jwt import create_access_token
from app.security.password import hash_password
from app.services.auth_service import authenticate_user

TEST_PASSWORD = "Phase3ATestPassword123!"


def _new_test_email() -> str:
    return f"phase3a-{uuid4().hex}@example.com"


def _create_test_user(mongo_db, role: str) -> dict:
    now = datetime.now(timezone.utc)
    user_id = next_sequence_id(mongo_db, "users")
    email = _new_test_email()
    mongo_db["users"].insert_one(
        {
            "id": user_id,
            "email": email,
            "full_name": f"Phase 3A {role.title()}",
            "password_hash": hash_password(TEST_PASSWORD),
            "role": role,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
    )
    return {"id": user_id, "email": email, "role": role}


def _login(client, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_test_created_account_uses_argon2id_and_rejects_wrong_password(client):
    mongo_db = get_mongo_database()
    email = _new_test_email()
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Phase 3A Password Test",
            "password": TEST_PASSWORD,
        },
    )
    assert registration.status_code == 201

    user = get_user_by_email(mongo_db, email)
    assert user is not None
    assert user.id == registration.json()["id"]
    assert user.email == email
    assert user.role == "student"
    assert user.is_active is True
    assert user.password_hash.startswith("$argon2id$")
    assert authenticate_user(mongo_db, email, "WrongTestPassword999!") is None


def test_test_created_account_authenticates_through_login_endpoint(client):
    mongo_db = get_mongo_database()
    email = _new_test_email()
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Phase 3A Login Test",
            "password": TEST_PASSWORD,
        },
    )
    assert registration.status_code == 201
    user_id = registration.json()["id"]

    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongTestPassword999!"},
    )
    assert bad_login.status_code == 401

    good_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": TEST_PASSWORD},
    )
    assert good_login.status_code == 200
    body = good_login.json()
    assert body["user"]["id"] == user_id
    assert body["user"]["email"] == email
    assert "password_hash" not in body["user"]

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["id"] == user_id


def test_registration_persists_to_mongodb_with_sequential_counter(client):
    mongo_db = get_mongo_database()
    before_seq = mongo_db[COUNTERS_COLLECTION].find_one({"_id": "users"})["seq"]
    email = _new_test_email()

    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email.upper(),
            "full_name": "Mongo Registered User",
            "password": "StrongPassword123!",
        },
    )
    assert reg.status_code == 201
    data = reg.json()
    assert data["email"] == email
    assert data["id"] == before_seq + 1
    assert data["role"] == "student"

    stored = mongo_db["users"].find_one({"id": data["id"]})
    assert stored is not None
    assert stored["email"] == email
    assert stored["password_hash"].startswith("$argon2id$")

    # Case-insensitive duplicate rejection
    dup = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Duplicate Attempt",
            "password": "StrongPassword123!",
        },
    )
    assert dup.status_code == 409


def test_expired_jwt_rejected_and_profile_and_password_update_persist(client):
    mongo_db = get_mongo_database()
    email = _new_test_email()
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Original Name",
            "password": "OldPassword123!",
        },
    )
    assert reg.status_code == 201
    user_id = reg.json()["id"]

    # Expired token -> 401
    expired_token = create_access_token(
        {"sub": str(user_id), "email": email, "role": "student", "full_name": "Original Name"},
        expires_delta=timedelta(seconds=-10),
    )
    expired_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert expired_res.status_code == 401
    assert "expired" in expired_res.json()["detail"].lower()

    # Valid login + profile update + password change
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "OldPassword123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    upd = client.put(
        "/api/v1/auth/profile",
        json={"full_name": "Updated Mongo Name"},
        headers=headers,
    )
    assert upd.status_code == 200
    assert upd.json()["full_name"] == "Updated Mongo Name"
    assert mongo_db["users"].find_one({"id": user_id})["full_name"] == "Updated Mongo Name"

    pwd_change = client.put(
        "/api/v1/auth/password",
        json={"current_password": "OldPassword123!", "new_password": "NewPassword456!"},
        headers=headers,
    )
    assert pwd_change.status_code == 200

    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "OldPassword123!"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "NewPassword456!"},
        ).status_code
        == 200
    )


def test_rbac_student_instructor_admin_permissions(client):
    mongo_db = get_mongo_database()
    student = _create_test_user(mongo_db, "student")
    instructor = _create_test_user(mongo_db, "instructor")
    admin = _create_test_user(mongo_db, "admin")
    student_h = _login(client, student["email"])
    inst_h = _login(client, instructor["email"])
    admin_h = _login(client, admin["email"])

    assert client.get("/api/v1/student/dashboard", headers=student_h).status_code == 200
    assert client.get("/api/v1/instructor/dashboard", headers=student_h).status_code == 403
    assert client.get("/api/v1/admin/users", headers=student_h).status_code == 403

    assert client.get("/api/v1/instructor/dashboard", headers=inst_h).status_code == 200
    assert client.get("/api/v1/student/dashboard", headers=inst_h).status_code == 403
    assert client.get("/api/v1/admin/users", headers=inst_h).status_code == 403

    users_res = client.get("/api/v1/admin/users", headers=admin_h)
    assert users_res.status_code == 200
    assert users_res.json()["total"] >= 3


def test_instructor_creation_password_setup_and_login_in_mongodb(client, monkeypatch):
    from urllib.parse import parse_qs, urlparse
    from app.routers import instructor_admin

    mongo_db = get_mongo_database()
    admin = _create_test_user(mongo_db, "admin")
    links = []
    monkeypatch.setattr(
        instructor_admin,
        "send_instructor_password_email",
        lambda user, profile, link, settings, purpose: links.append(link),
    )
    admin_h = _login(client, admin["email"])

    email = _new_test_email()
    created = client.post(
        "/api/v1/admin/instructors",
        json={
            "full_name": "Mongo Instructor",
            "email": email,
            "phone_number": "15550100",
            "qualification": "PhD CS",
            "department": "Computer Science",
            "subject_expertise": "Databases",
            "experience_years": 5,
        },
        headers=admin_h,
    )
    assert created.status_code == 201
    user_id = created.json()["user_id"]

    token = parse_qs(urlparse(links[0]).query)["token"][0]
    setup = client.post(
        "/api/v1/auth/instructor-password",
        json={"token": token, "new_password": "InstructorTestPass456!"},
    )
    assert setup.status_code == 200

    inst_login = client.post(
        "/api/v1/auth/instructor-login",
        json={"email": email, "password": "InstructorTestPass456!"},
    )
    assert inst_login.status_code == 200
    assert inst_login.json()["user"]["id"] == user_id
    assert inst_login.json()["user"]["role"] == "instructor"

    # Single-use token cannot be reused
    reuse = client.post(
        "/api/v1/auth/instructor-password",
        json={"token": token, "new_password": "AnotherTestPass789!"},
    )
    assert reuse.status_code == 400


def test_registration_rolls_back_mongodb_when_sqlite_shadow_sync_fails(monkeypatch):
    import pytest
    from sqlalchemy.exc import SQLAlchemyError
    from app.schemas.user import UserCreate
    from app.services import auth_service

    mongo_db = get_mongo_database()
    email = _new_test_email()

    def fail_shadow(*args, **kwargs):
        raise SQLAlchemyError("simulated sqlite shadow failure")

    monkeypatch.setattr(auth_service, "sync_user_to_sqlite_shadow", fail_shadow)

    with pytest.raises(SQLAlchemyError):
        auth_service.register_user(
            mongo_db,
            UserCreate(email=email, full_name="Rollback Test", password="StrongPassword123!"),
            sqlite_db=object(),  # type: ignore[arg-type]
        )

    assert get_user_by_email(mongo_db, email) is None
