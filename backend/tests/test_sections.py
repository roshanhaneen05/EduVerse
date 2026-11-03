import pytest


def get_token(client, email, password="EduVerseDemo2026!"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


def test_create_and_list_sections(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    headers = {"Authorization": f"Bearer {sarah_token}"}

    # 1. Create a section for course 1
    create_resp = client.post(
        "/api/v1/instructor/courses/1/sections",
        json={"title": "Module 1: Foundations", "description": "Core principles", "order_index": 1},
        headers=headers,
    )
    assert create_resp.status_code == 201
    sec1 = create_resp.json()
    assert sec1["title"] == "Module 1: Foundations"
    assert sec1["course_id"] == 1
    assert sec1["order_index"] == 1

    # 2. Create a second section
    create_resp2 = client.post(
        "/api/v1/instructor/courses/1/sections",
        json={"title": "Module 2: Advanced Concepts", "order_index": 2},
        headers=headers,
    )
    assert create_resp2.status_code == 201
    sec2 = create_resp2.json()

    # 3. List sections via instructor endpoint
    list_resp = client.get("/api/v1/instructor/courses/1/sections", headers=headers)
    assert list_resp.status_code == 200
    sections = list_resp.json()
    assert len(sections) >= 2
    assert any(s["id"] == sec1["id"] for s in sections)
    assert any(s["id"] == sec2["id"] for s in sections)


def test_update_and_reorder_sections(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    headers = {"Authorization": f"Bearer {sarah_token}"}

    # Create sections to reorder
    s1 = client.post(
        "/api/v1/instructor/courses/1/sections",
        json={"title": "Reorder A", "order_index": 10},
        headers=headers,
    ).json()
    s2 = client.post(
        "/api/v1/instructor/courses/1/sections",
        json={"title": "Reorder B", "order_index": 20},
        headers=headers,
    ).json()

    # Update title
    update_resp = client.put(
        f"/api/v1/instructor/sections/{s1['id']}",
        json={"title": "Reorder A Updated", "description": "Updated description"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Reorder A Updated"
    assert update_resp.json()["description"] == "Updated description"

    # Batch reorder
    reorder_resp = client.post(
        "/api/v1/instructor/courses/1/sections/reorder",
        json=[
            {"section_id": s1["id"], "order_index": 20},
            {"section_id": s2["id"], "order_index": 10},
        ],
        headers=headers,
    )
    assert reorder_resp.status_code == 200

    # Verify order swapped
    sections = client.get("/api/v1/instructor/courses/1/sections", headers=headers).json()
    sec_map = {s["id"]: s["order_index"] for s in sections}
    assert sec_map[s1["id"]] == 20
    assert sec_map[s2["id"]] == 10


def test_assign_lesson_to_section(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    headers = {"Authorization": f"Bearer {sarah_token}"}

    # Create a section
    sec = client.post(
        "/api/v1/instructor/courses/1/sections",
        json={"title": "Assignment Target Section", "order_index": 5},
        headers=headers,
    ).json()

    # Create a lesson in course 1
    lesson = client.post(
        "/api/v1/instructor/courses/1/lessons",
        json={"title": "Test Lesson For Section", "content": "Content here", "order_index": 10},
        headers=headers,
    ).json()
    assert lesson["section_id"] is None

    # Assign lesson to section
    assign_resp = client.put(
        f"/api/v1/instructor/lessons/{lesson['id']}/assign-section",
        json={"section_id": sec["id"], "order_index": 1},
        headers=headers,
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["section_id"] == sec["id"]

    # Verify course detail reflects section
    course_detail = client.get("/api/v1/courses/1").json()
    assert "sections" in course_detail
    matched_sec = next((s for s in course_detail["sections"] if s["id"] == sec["id"]), None)
    assert matched_sec is not None
    assert any(l["id"] == lesson["id"] for l in matched_sec["lessons"])


def test_safe_section_deletion(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    headers = {"Authorization": f"Bearer {sarah_token}"}

    # Create source section and target section
    sec_source = client.post(
        "/api/v1/instructor/courses/1/sections",
        json={"title": "Source Section To Delete", "order_index": 30},
        headers=headers,
    ).json()
    sec_target = client.post(
        "/api/v1/instructor/courses/1/sections",
        json={"title": "Target Section For Reassignment", "order_index": 31},
        headers=headers,
    ).json()

    # Create a lesson in source section
    lesson = client.post(
        "/api/v1/instructor/courses/1/lessons",
        json={
            "title": "Lesson Inside Source Section",
            "content": "Lesson content",
            "order_index": 1,
            "section_id": sec_source["id"],
        },
        headers=headers,
    ).json()
    assert lesson["section_id"] == sec_source["id"]

    # 1. Attempt to delete section WITHOUT reassign_to_section_id -> Must be REJECTED (HTTP 400)
    del_resp = client.delete(f"/api/v1/instructor/sections/{sec_source['id']}", headers=headers)
    assert del_resp.status_code == 400
    assert "contains lessons" in del_resp.json()["detail"]

    # 2. Delete section WITH reassign_to_section_id -> Must SUCCEED and move lesson
    del_reassign_resp = client.delete(
        f"/api/v1/instructor/sections/{sec_source['id']}?reassign_to_section_id={sec_target['id']}",
        headers=headers,
    )
    assert del_reassign_resp.status_code == 200

    # Verify lesson was moved to target section
    lesson_check = client.get(f"/api/v1/lessons/{lesson['id']}", headers=headers).json()
    assert lesson_check["section_id"] == sec_target["id"]

    # Verify source section is gone
    sec_check = client.get(
        f"/api/v1/instructor/courses/1/sections",
        headers=headers,
    ).json()
    assert not any(s["id"] == sec_source["id"] for s in sec_check)


def test_section_authorization_enforcement(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    marcus_token = get_token(client, "marcus.vance@eduverse.io")
    alex_token = get_token(client, "alex.rivera@eduverse.io")

    # Sarah owns course 1, Marcus owns course 2
    # Marcus attempts to create section in Course 1 -> 403 Forbidden
    marcus_headers = {"Authorization": f"Bearer {marcus_token}"}
    res = client.post(
        "/api/v1/instructor/courses/1/sections",
        json={"title": "Unauthorized Section"},
        headers=marcus_headers,
    )
    assert res.status_code == 403

    # Student attempts to create section in Course 1 -> 403 Forbidden
    alex_headers = {"Authorization": f"Bearer {alex_token}"}
    res_student = client.post(
        "/api/v1/instructor/courses/1/sections",
        json={"title": "Student Section"},
        headers=alex_headers,
    )
    assert res_student.status_code == 403

    # Public endpoint allows anyone (including student) to read sections
    public_res = client.get("/api/v1/courses/1/sections")
    assert public_res.status_code == 200
    assert isinstance(public_res.json(), list)

