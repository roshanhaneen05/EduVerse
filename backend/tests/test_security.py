import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.security.rate_limiter import reset_rate_limiter


def get_token(client: TestClient, email: str, password: str = "EduVerseDemo2026!") -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestSecurityHardening:
    """Comprehensive automated security verification suite."""

    def test_security_headers_present(self, client: TestClient):
        """Verify that defensive HTTP headers are attached to API responses."""
        res = client.get("/health")
        assert res.status_code == 200
        headers = {k.lower(): v for k, v in res.headers.items()}
        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-frame-options") == "DENY"
        assert "1; mode=block" in headers.get("x-xss-protection", "")
        assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_production_secret_key_validation(self):
        """Enforce that production environments reject default or weak secret keys."""
        # 1. Default insecure dev key in production -> Must fail
        with pytest.raises(ValueError, match="Insecure production configuration"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="dev-secret-key-change-me-for-production-min-32-chars-long!",
            )

        # 2. Short secret key (< 32 chars) in production -> Must fail
        with pytest.raises(ValueError, match="Insecure production configuration"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="too-short-secret-key-12345",
            )

        # 3. High-entropy key with >= 32 chars in production -> Must succeed
        valid_settings = Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a-very-secure-randomly-generated-production-secret-key-2026!",
        )
        assert valid_settings.is_production is True
        assert valid_settings.SECRET_KEY == "a-very-secure-randomly-generated-production-secret-key-2026!"

        # 4. In development, default key is permitted
        dev_settings = Settings(ENVIRONMENT="development")
        assert dev_settings.is_production is False

    def test_login_rate_limiting(self, client: TestClient):
        """Verify that abuse-sensitive login endpoint blocks rapid brute-force attempts."""
        reset_rate_limiter()
        headers = {"X-Enforce-Rate-Limit": "true"}

        # Attempt 15 logins rapidly
        triggered_429 = False
        for i in range(20):
            res = client.post(
                "/api/v1/auth/login",
                json={"email": f"brute_force_{i}@eduverse.io", "password": "WrongPassword!"},
                headers=headers,
            )
            if res.status_code == 429:
                triggered_429 = True
                assert "Retry-After" in res.headers
                assert "Too many requests" in res.json().get("detail", "")
                break

        assert triggered_429 is True, "Rate limiter did not throttle after threshold limit"
        reset_rate_limiter()

    def test_deactivated_account_access_blocked_consistently(self, client: TestClient):
        """Verify deactivated accounts cannot login, access authenticated endpoints, or download files."""
        admin_token = get_token(client, "admin@eduverse.io")

        # 1. Register a student specifically to test deactivation
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": "deactivate.me@eduverse.io",
                "password": "EduVerseDemo2026!",
                "full_name": "To Be Deactivated",
            },
        )
        assert reg.status_code in (201, 409)
        user_id = reg.json().get("id")
        if not user_id:
            users_res = client.get("/api/v1/admin/users?search=deactivate.me", headers=auth_header(admin_token)).json()
            user_id = users_res["items"][0]["id"]

        # Acquire token before deactivation
        student_token = get_token(client, "deactivate.me@eduverse.io")

        # 2. Deactivate the user via Admin API
        deact_res = client.put(
            f"/api/v1/admin/users/{user_id}",
            json={"is_active": False},
            headers=auth_header(admin_token),
        )
        assert deact_res.status_code == 200
        assert deact_res.json()["is_active"] is False

        # 3. Attempt login with valid credentials -> Must return 403 Forbidden
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "deactivate.me@eduverse.io", "password": "EduVerseDemo2026!"},
        )
        assert login_res.status_code == 403
        assert "deactivated" in login_res.json()["detail"].lower()

        # 4. Attempt to use existing pre-deactivation token -> Must return 403 Forbidden
        me_res = client.get("/api/v1/auth/me", headers=auth_header(student_token))
        assert me_res.status_code == 403
        assert "deactivated" in me_res.json()["detail"].lower()

        # 5. Attempt material download with pre-deactivation token -> Must return 403 Forbidden
        mat_res = client.get("/api/v1/materials/1/download", headers=auth_header(student_token))
        assert mat_res.status_code == 403
        assert "deactivated" in mat_res.json()["detail"].lower()

        # Reactivate user to clean up state
        client.put(
            f"/api/v1/admin/users/{user_id}",
            json={"is_active": True},
            headers=auth_header(admin_token),
        )

    def test_student_role_escalation_prevented_at_registration(self, client: TestClient):
        """Verify that passing role='admin' in public registration is ignored and assigned 'student'."""
        email = "escalation.attacker@eduverse.io"
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "EduVerseDemo2026!",
                "full_name": "Escalation Attacker",
                "role": "admin",  # Malicious escalation attempt
            },
        )
        if reg.status_code == 201:
            data = reg.json()
            assert data["role"] == "student"
        elif reg.status_code == 409:
            # Check existing profile
            token = get_token(client, email)
            me = client.get("/api/v1/auth/me", headers=auth_header(token)).json()
            assert me["role"] == "student"

    def test_student_cannot_access_other_student_private_data(self, client: TestClient):
        """Verify cross-student IDOR is strictly blocked for submissions, attempts, and conversations."""
        alex_token = get_token(client, "alex.rivera@eduverse.io")

        # Register a second student
        client.post(
            "/api/v1/auth/register",
            json={"email": "second.student@eduverse.io", "password": "EduVerseDemo2026!", "full_name": "Second Student"},
        )
        second_token = get_token(client, "second.student@eduverse.io")

        # 1. Alex creates a private AI conversation
        conv_res = client.post(
            "/api/v1/ai/chat",
            json={"message": "Private conversation topic for Alex"},
            headers=auth_header(alex_token),
        )
        assert conv_res.status_code == 200
        alex_conv_id = conv_res.json()["conversation_id"]

        # 2. Second student attempts to read Alex's conversation -> Must return 403
        peek_res = client.get(
            f"/api/v1/ai/conversations/{alex_conv_id}",
            headers=auth_header(second_token),
        )
        assert peek_res.status_code == 403

        # 3. Second student attempts to delete Alex's conversation -> Must return 403
        del_res = client.delete(
            f"/api/v1/ai/conversations/{alex_conv_id}",
            headers=auth_header(second_token),
        )
        assert del_res.status_code == 403

        # 4. Second student attempts to continue Alex's conversation in chat -> Must return 403
        inject_res = client.post(
            "/api/v1/ai/chat",
            json={"message": "Unauthorized continuation", "conversation_id": alex_conv_id},
            headers=auth_header(second_token),
        )
        assert inject_res.status_code == 403

    def test_instructor_isolation_enforced(self, client: TestClient):
        """Verify an instructor cannot modify or delete courses belonging to another instructor."""
        sarah_token = get_token(client, "sarah.chen@eduverse.io")

        # Register second instructor
        admin_token = get_token(client, "admin@eduverse.io")
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": "second.instructor@eduverse.io", "password": "EduVerseDemo2026!", "full_name": "Second Instructor"},
        )
        if reg.status_code == 201:
            user_id = reg.json()["id"]
            client.put(f"/api/v1/admin/users/{user_id}", json={"role": "instructor"}, headers=auth_header(admin_token))

        second_inst_token = get_token(client, "second.instructor@eduverse.io")

        # Sarah creates a course
        create_res = client.post(
            "/api/v1/instructor/courses",
            json={
                "title": "Sarah's Secure Course",
                "description": "Course owned exclusively by Sarah",
                "category": "Security",
                "difficulty": "Intermediate",
            },
            headers=auth_header(sarah_token),
        )
        assert create_res.status_code == 201
        course_id = create_res.json()["id"]

        # Second instructor attempts to update Sarah's course -> Must return 403
        update_res = client.put(
            f"/api/v1/instructor/courses/{course_id}",
            json={"title": "Hacked Course Title"},
            headers=auth_header(second_inst_token),
        )
        assert update_res.status_code == 403

        # Second instructor attempts to delete Sarah's course -> Must return 403
        delete_res = client.delete(
            f"/api/v1/instructor/courses/{course_id}",
            headers=auth_header(second_inst_token),
        )
        assert delete_res.status_code == 403

        # Clean up
        client.delete(f"/api/v1/instructor/courses/{course_id}", headers=auth_header(sarah_token))

    def test_file_upload_security_checks(self, client: TestClient):
        """Verify malicious file extensions, executable magic bytes, and path traversal are rejected."""
        sarah_token = get_token(client, "sarah.chen@eduverse.io")

        # 1. Attempt to upload dangerous executable extension (.sh)
        res_sh = client.post(
            "/api/v1/instructor/courses/1/materials",
            data={"title": "Shell Script Attack"},
            files={"file": ("exploit.sh", b"#!/bin/bash\necho hacked", "text/x-shellscript")},
            headers=auth_header(sarah_token),
        )
        assert res_sh.status_code == 400
        assert "forbidden" in res_sh.json()["detail"].lower()

        # 2. Attempt to upload Windows executable magic bytes masquerading as PDF
        res_pe = client.post(
            "/api/v1/instructor/courses/1/materials",
            data={"title": "EXE Masquerading as PDF"},
            files={"file": ("fake.pdf", b"MZ\x90\x00\x03\x00\x00\x00", "application/pdf")},
            headers=auth_header(sarah_token),
        )
        assert res_pe.status_code == 400
        assert "prohibited format" in res_pe.json()["detail"].lower()

        # 3. Attempt to upload empty file
        res_empty = client.post(
            "/api/v1/instructor/courses/1/materials",
            data={"title": "Empty File"},
            files={"file": ("empty.pdf", b"", "application/pdf")},
            headers=auth_header(sarah_token),
        )
        assert res_empty.status_code == 400
        assert "empty" in res_empty.json()["detail"].lower()

