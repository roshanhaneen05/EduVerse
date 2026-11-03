import pytest
from app.models.user import User


def get_token(client, email: str, password: str = "EduVerseDemo2026!") -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.status_code}"
    return res.json()["access_token"]


def test_admin_endpoints_require_admin_role(client):
    # Student attempting to access admin stats -> 403 Forbidden
    student_token = get_token(client, "alex.rivera@eduverse.io")
    student_headers = {"Authorization": f"Bearer {student_token}"}
    forbidden_resp = client.get("/api/v1/admin/stats", headers=student_headers)
    assert forbidden_resp.status_code == 403

    # Instructor attempting to access admin stats -> 403 Forbidden
    instructor_token = get_token(client, "sarah.chen@eduverse.io")
    instructor_headers = {"Authorization": f"Bearer {instructor_token}"}
    inst_forbidden = client.get("/api/v1/admin/stats", headers=instructor_headers)
    assert inst_forbidden.status_code == 403

    # Admin access -> 200 OK
    admin_token = get_token(client, "admin@eduverse.io")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    stats_resp = client.get("/api/v1/admin/stats", headers=admin_headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_users"] >= 1
    assert stats["total_courses"] >= 1
    assert stats["total_students"] >= 1
    assert stats["total_instructors"] >= 1
    assert stats["total_admins"] >= 1
    assert "recent_activities" in stats
    assert isinstance(stats["recent_activities"], list)


def test_admin_user_listing_and_filtering(client):
    admin_token = get_token(client, "admin@eduverse.io")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Paginated user listing
    res = client.get("/api/v1/admin/users?page=1&page_size=5", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data
    assert "items" in data
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert len(data["items"]) <= 5
    assert data["total"] >= len(data["items"])

    # Verify no password hashes are exposed
    for u in data["items"]:
        assert "password_hash" not in u
        assert "password" not in u
        assert "email" in u
        assert "role" in u
        assert "is_active" in u

    # 2. Filter by role
    res_students = client.get("/api/v1/admin/users?role=student", headers=headers)
    assert res_students.status_code == 200
    for u in res_students.json()["items"]:
        assert u["role"] == "student"

    res_instructors = client.get("/api/v1/admin/users?role=instructor", headers=headers)
    assert res_instructors.status_code == 200
    for u in res_instructors.json()["items"]:
        assert u["role"] == "instructor"

    # 3. Filter by search
    res_search = client.get("/api/v1/admin/users?search=alex", headers=headers)
    assert res_search.status_code == 200
    found = res_search.json()["items"]
    assert len(found) >= 1
    assert any("alex" in u["email"].lower() or "alex" in u["full_name"].lower() for u in found)

    # 4. Filter by active status
    res_active = client.get("/api/v1/admin/users?is_active=true", headers=headers)
    assert res_active.status_code == 200
    for u in res_active.json()["items"]:
        assert u["is_active"] is True


def test_admin_self_deactivation_prevention(client):
    admin_token = get_token(client, "admin@eduverse.io")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Get admin's own ID
    me_res = client.get("/api/v1/admin/users?search=admin@eduverse.io", headers=headers)
    assert me_res.status_code == 200
    admin_user = me_res.json()["items"][0]
    admin_id = admin_user["id"]

    # Try deactivating self
    deact_res = client.put(
        f"/api/v1/admin/users/{admin_id}",
        json={"is_active": False},
        headers=headers,
    )
    assert deact_res.status_code == 400
    assert "cannot deactivate their own account" in deact_res.json()["detail"].lower()


def test_admin_self_demotion_prevention(client):
    admin_token = get_token(client, "admin@eduverse.io")
    headers = {"Authorization": f"Bearer {admin_token}"}

    me_res = client.get("/api/v1/admin/users?search=admin@eduverse.io", headers=headers)
    assert me_res.status_code == 200
    admin_user = me_res.json()["items"][0]
    admin_id = admin_user["id"]

    # Try demoting self to student
    demote_res = client.put(
        f"/api/v1/admin/users/{admin_id}",
        json={"role": "student"},
        headers=headers,
    )
    assert demote_res.status_code == 400
    assert "cannot demote" in demote_res.json()["detail"].lower()


def test_admin_user_role_and_name_update(client):
    admin_token = get_token(client, "admin@eduverse.io")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Register a new dummy user to update
    dummy_email = "phase6.test.user@eduverse.io"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": dummy_email,
            "password": "EduVerseDemo2026!",
            "full_name": "Phase Six User",
        },
    )

    # Find the user
    user_res = client.get(f"/api/v1/admin/users?search={dummy_email}", headers=headers)
    assert user_res.status_code == 200
    target_user = user_res.json()["items"][0]
    user_id = target_user["id"]

    # Promote to instructor
    promote_res = client.put(
        f"/api/v1/admin/users/{user_id}",
        json={"role": "instructor", "full_name": "Phase Six Instructor"},
        headers=headers,
    )
    assert promote_res.status_code == 200
    updated = promote_res.json()
    assert updated["role"] == "instructor"
    assert updated["full_name"] == "Phase Six Instructor"

    # Reject invalid role
    invalid_role_res = client.put(
        f"/api/v1/admin/users/{user_id}",
        json={"role": "superhero"},
        headers=headers,
    )
    assert invalid_role_res.status_code == 400


def test_admin_user_deactivation_and_login_blocking(client):
    admin_token = get_token(client, "admin@eduverse.io")
    headers = {"Authorization": f"Bearer {admin_token}"}

    target_email = "alex.rivera@eduverse.io"
    user_res = client.get(f"/api/v1/admin/users?search={target_email}", headers=headers)
    assert user_res.status_code == 200
    user_id = user_res.json()["items"][0]["id"]

    # 1. Deactivate student
    deact_res = client.put(
        f"/api/v1/admin/users/{user_id}",
        json={"is_active": False},
        headers=headers,
    )
    assert deact_res.status_code == 200
    assert deact_res.json()["is_active"] is False

    # 2. Student login should now fail with 403 Forbidden
    login_attempt = client.post(
        "/api/v1/auth/login",
        json={"email": target_email, "password": "EduVerseDemo2026!"},
    )
    assert login_attempt.status_code == 403
    assert "deactivated" in login_attempt.json()["detail"].lower()

    # 3. Reactivate student
    react_res = client.put(
        f"/api/v1/admin/users/{user_id}",
        json={"is_active": True},
        headers=headers,
    )
    assert react_res.status_code == 200
    assert react_res.json()["is_active"] is True

    # 4. Student can log in again
    login_success = client.post(
        "/api/v1/auth/login",
        json={"email": target_email, "password": "EduVerseDemo2026!"},
    )
    assert login_success.status_code == 200


def test_admin_course_listing_and_filtering(client):
    admin_token = get_token(client, "admin@eduverse.io")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. List all platform courses
    res = client.get("/api/v1/admin/courses?page=1&page_size=5", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data
    assert "items" in data
    assert data["total"] >= 1
    assert len(data["items"]) >= 1

    first_course = data["items"][0]
    assert "id" in first_course
    assert "title" in first_course
    assert "category" in first_course
    assert "difficulty" in first_course
    assert "is_published" in first_course
    assert "instructor_name" in first_course
    assert "instructor_email" in first_course
    assert "enrolled_students_count" in first_course
    assert "lesson_count" in first_course
    assert "quiz_count" in first_course
    assert "assignment_count" in first_course

    # 2. Filter by is_published
    res_pub = client.get("/api/v1/admin/courses?is_published=true", headers=headers)
    assert res_pub.status_code == 200
    for c in res_pub.json()["items"]:
        assert c["is_published"] is True

    # 3. Search courses
    course_title_word = first_course["title"].split()[0]
    res_search = client.get(f"/api/v1/admin/courses?search={course_title_word}", headers=headers)
    assert res_search.status_code == 200
    assert len(res_search.json()["items"]) >= 1


def test_admin_course_categories(client):
    admin_token = get_token(client, "admin@eduverse.io")
    headers = {"Authorization": f"Bearer {admin_token}"}

    res = client.get("/api/v1/admin/courses/categories", headers=headers)
    assert res.status_code == 200
    categories = res.json()
    assert isinstance(categories, list)
    assert len(categories) >= 1


def test_admin_course_publication_toggle(client):
    admin_token = get_token(client, "admin@eduverse.io")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Get first course
    list_res = client.get("/api/v1/admin/courses", headers=headers)
    assert list_res.status_code == 200
    course = list_res.json()["items"][0]
    course_id = course["id"]
    initial_status = course["is_published"]

    # Toggle publish
    toggle_res1 = client.patch(f"/api/v1/admin/courses/{course_id}/publish", headers=headers)
    assert toggle_res1.status_code == 200
    assert toggle_res1.json()["is_published"] == (not initial_status)

    # Toggle back to restore initial state
    toggle_res2 = client.patch(f"/api/v1/admin/courses/{course_id}/publish", headers=headers)
    assert toggle_res2.status_code == 200
    assert toggle_res2.json()["is_published"] == initial_status


def test_student_and_instructor_denied_from_all_admin_endpoints(client):
    student_token = get_token(client, "alex.rivera@eduverse.io")
    student_headers = {"Authorization": f"Bearer {student_token}"}

    instructor_token = get_token(client, "sarah.chen@eduverse.io")
    instructor_headers = {"Authorization": f"Bearer {instructor_token}"}

    endpoints = [
        ("GET", "/api/v1/admin/stats"),
        ("GET", "/api/v1/admin/users"),
        ("PUT", "/api/v1/admin/users/1"),
        ("GET", "/api/v1/admin/courses"),
        ("GET", "/api/v1/admin/courses/categories"),
        ("PATCH", "/api/v1/admin/courses/1/publish"),
    ]

    for method, endpoint in endpoints:
        # Student check
        if method == "GET":
            s_res = client.get(endpoint, headers=student_headers)
            i_res = client.get(endpoint, headers=instructor_headers)
        elif method == "PUT":
            s_res = client.put(endpoint, json={"role": "admin"}, headers=student_headers)
            i_res = client.put(endpoint, json={"role": "admin"}, headers=instructor_headers)
        elif method == "PATCH":
            s_res = client.patch(endpoint, headers=student_headers)
            i_res = client.patch(endpoint, headers=instructor_headers)

        assert s_res.status_code == 403, f"Student was not blocked from {method} {endpoint}"
        assert i_res.status_code == 403, f"Instructor was not blocked from {method} {endpoint}"


def test_admin_not_found_handling(client):
    admin_token = get_token(client, "admin@eduverse.io")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Non-existent user
    u_res = client.put("/api/v1/admin/users/999999", json={"role": "student"}, headers=headers)
    assert u_res.status_code == 404

    # Non-existent course toggle
    c_res = client.patch("/api/v1/admin/courses/999999/publish", headers=headers)
    assert c_res.status_code == 404
