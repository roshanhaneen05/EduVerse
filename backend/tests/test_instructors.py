from urllib.parse import parse_qs, urlparse

from app.routers import instructor_admin


def _admin_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@eduverse.io", "password": "EduVerseDemo2026!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _instructor_payload(email="faculty.new@eduverse.io"):
    return {
        "full_name": "Faculty Member",
        "email": email,
        "phone_number": "15550100",
        "qualification": "MSc Computer Science",
        "department": "Computer Science",
        "subject_expertise": "Distributed Systems",
        "experience_years": 8,
    }


def test_public_registration_cannot_create_instructors(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Unapproved Instructor",
            "email": "public.instructor@eduverse.io",
            "password": "SecurePassword123!",
            "role": "instructor",
        },
    )

    assert response.status_code == 403
    assert "administrator" in response.json()["detail"].lower()


def test_admin_creates_and_manages_instructor_password(client, monkeypatch):
    setup_links = []
    monkeypatch.setattr(
        instructor_admin,
        "send_instructor_password_email",
        lambda user, profile, link, settings, purpose: setup_links.append((link, purpose)),
    )
    headers = _admin_headers(client)

    created = client.post(
        "/api/v1/admin/instructors",
        json=_instructor_payload(),
        headers=headers,
    )
    assert created.status_code == 201
    instructor = created.json()
    assert instructor["email"] == "faculty.new@eduverse.io"
    assert instructor["instructor_id"].startswith("EV-I-")
    assert instructor["is_active"] is True
    assert instructor["department"] == "Computer Science"
    assert instructor["email_delivery_status"] == "sent"
    assert setup_links[0][1] == "setup"

    parsed_link = urlparse(setup_links[0][0])
    token = parse_qs(parsed_link.query)["token"][0]
    password_response = client.post(
        "/api/v1/auth/instructor-password",
        json={"token": token, "new_password": "NewFacultyPassword123!"},
    )
    assert password_response.status_code == 200

    instructor_login = client.post(
        "/api/v1/auth/instructor-login",
        json={"email": instructor["email"], "password": "NewFacultyPassword123!"},
    )
    assert instructor_login.status_code == 200
    assert instructor_login.json()["user"]["role"] == "instructor"

    reset = client.post(
        f"/api/v1/admin/instructors/{instructor['user_id']}/password-reset",
        headers=_admin_headers(client),
    )
    assert reset.status_code == 200
    assert setup_links[-1][1] == "reset"
    reset_token = parse_qs(urlparse(setup_links[-1][0]).query)["token"][0]
    changed_password = client.post(
        "/api/v1/auth/instructor-password",
        json={"token": reset_token, "new_password": "ResetFacultyPassword123!"},
    )
    assert changed_password.status_code == 200
    assert client.post(
        "/api/v1/auth/instructor-login",
        json={"email": instructor["email"], "password": "ResetFacultyPassword123!"},
    ).status_code == 200

    updated = client.put(
        f"/api/v1/admin/instructors/{instructor['user_id']}",
        json={"department": "Applied Computing", "experience_years": 9},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["department"] == "Applied Computing"
    assert updated.json()["experience_years"] == 9

    repeated_token = client.post(
        "/api/v1/auth/instructor-password",
        json={"token": token, "new_password": "AnotherFacultyPassword123!"},
    )
    assert repeated_token.status_code == 400

    duplicate = client.post(
        "/api/v1/admin/instructors",
        json=_instructor_payload(),
        headers=headers,
    )
    assert duplicate.status_code == 409
    deleted = client.delete(
        f"/api/v1/admin/instructors/{instructor['user_id']}",
        headers=headers,
    )
    assert deleted.status_code == 200


def test_instructor_management_requires_admin(client):
    student_login = client.post(
        "/api/v1/auth/login",
        json={"email": "alex.rivera@eduverse.io", "password": "EduVerseDemo2026!"},
    )
    response = client.get(
        "/api/v1/admin/instructors",
        headers={"Authorization": f"Bearer {student_login.json()['access_token']}"},
    )
    assert response.status_code == 403


def test_admin_can_deactivate_instructor_and_delete_only_after_course_reassignment(
    client,
    monkeypatch,
):
    monkeypatch.setattr(instructor_admin, "send_instructor_password_email", lambda *args: None)
    monkeypatch.setattr(instructor_admin, "send_instructor_status_email", lambda *args: None)
    headers = _admin_headers(client)
    created = client.post(
        "/api/v1/admin/instructors",
        json=_instructor_payload("faculty.status@eduverse.io"),
        headers=headers,
    )
    assert created.status_code == 201
    instructor = created.json()
    user_id = instructor["user_id"]
    profile_response = client.get(
        f"/api/v1/admin/instructors/{user_id}",
        headers=headers,
    )
    assert profile_response.status_code == 200

    status_response = client.patch(
        f"/api/v1/admin/instructors/{user_id}/status",
        json={"is_active": False},
        headers=headers,
    )
    assert status_response.status_code == 200
    assert status_response.json()["is_active"] is False
    blocked_login = client.post(
        "/api/v1/auth/instructor-login",
        json={"email": instructor["email"], "password": "TemporaryPassword123!"},
    )
    assert blocked_login.status_code == 401

    reactivated = client.patch(
        f"/api/v1/admin/instructors/{user_id}/status",
        json={"is_active": True},
        headers=headers,
    )
    assert reactivated.status_code == 200
    courses = client.get("/api/v1/admin/courses?page=1&page_size=1", headers=headers)
    assert courses.status_code == 200
    course_id = courses.json()["items"][0]["id"]
    assigned = client.put(
        f"/api/v1/admin/courses/{course_id}/instructor",
        json={"instructor_user_id": user_id},
        headers=headers,
    )
    assert assigned.status_code == 200

    delete_blocked = client.delete(
        f"/api/v1/admin/instructors/{user_id}",
        headers=headers,
    )
    assert delete_blocked.status_code == 409


def test_instructor_filters_and_duplicate_email(client, monkeypatch):
    def smtp_failure(*args):
        raise OSError("SMTP server is unavailable")

    monkeypatch.setattr(instructor_admin, "send_instructor_password_email", smtp_failure)
    headers = _admin_headers(client)
    first = client.post(
        "/api/v1/admin/instructors",
        json=_instructor_payload("faculty.filter@eduverse.io"),
        headers=headers,
    )
    assert first.status_code == 201
    assert first.json()["email_delivery_status"] == "failed"

    filters = client.get(
        "/api/v1/admin/instructors?search=EV-I&department=Computer&is_active=true",
        headers=headers,
    )
    assert filters.status_code == 200
    assert any(item["user_id"] == first.json()["user_id"] for item in filters.json())

    duplicate = client.post(
        "/api/v1/admin/instructors",
        json=_instructor_payload("faculty.filter@eduverse.io"),
        headers=headers,
    )
    assert duplicate.status_code == 409
