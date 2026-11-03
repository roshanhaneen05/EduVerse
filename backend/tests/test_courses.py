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


def test_enrollment_and_duplicate_prevention(client):
    # Log in as test student
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "new.student@eduverse.io", "password": "SecurePassword123!"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Enroll in course 2
    enroll_resp = client.post("/api/v1/courses/2/enroll", headers=headers)
    assert enroll_resp.status_code == 201

    # Attempt duplicate enrollment -> should return 409
    dup_resp = client.post("/api/v1/courses/2/enroll", headers=headers)
    assert dup_resp.status_code == 409


def test_lesson_completion_and_progress_recalculation(client):
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "new.student@eduverse.io", "password": "SecurePassword123!"},
    )
    token = login_resp.json()["access_token"]
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

