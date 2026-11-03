import pytest


def get_auth_token(client, email, password="EduVerseDemo2026!"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        return resp.json()["access_token"]
    # Fallback to SecurePassword123!
    resp2 = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    if resp2.status_code == 200:
        return resp2.json()["access_token"]
    # Register if not present
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "full_name": "Test User",
        "password": "SecurePassword123!"
    })
    if reg_resp.status_code in (200, 201):
        login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
        if login_resp.status_code == 200:
            return login_resp.json()["access_token"]
    raise AssertionError(f"Could not authenticate {email}")


def test_quiz_student_view_hides_answers(client):
    token = get_auth_token(client, "new.student@eduverse.io")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/courses/2/enroll", headers=headers)

    # Course 2 quiz
    resp = client.get("/api/v1/quizzes/2", headers=headers)
    assert resp.status_code == 200
    quiz_data = resp.json()
    assert len(quiz_data["questions"]) >= 1

    # Ensure is_correct is NOT exposed in the student view before submission
    for q in quiz_data["questions"]:
        for opt in q["options"]:
            assert "is_correct" not in opt


def test_quiz_submission_and_scoring(client):
    token = get_auth_token(client, "new.student@eduverse.io")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/courses/2/enroll", headers=headers)

    # Submit answers
    submission_payload = {"answers": {}}
    sub_resp = client.post("/api/v1/quizzes/2/submit", headers=headers, json=submission_payload)
    assert sub_resp.status_code == 200
    res_data = sub_resp.json()
    assert "score" in res_data
    assert "passed" in res_data
    assert res_data["total_questions"] >= 1
    # Post-submission review is provided
    assert len(res_data["questions_review"]) >= 1
    assert len(res_data["answers"]) >= 1


def test_instructor_quiz_lifecycle(client):
    inst_token = get_auth_token(client, "sarah.chen@eduverse.io")
    inst_headers = {"Authorization": f"Bearer {inst_token}"}

    # 1. Create a quiz as instructor for Course 1
    quiz_payload = {
        "title": "Phase 4 Automated Assessment",
        "description": "Comprehensive quiz on full-stack architecture.",
        "passing_score": 80,
        "is_published": False,
        "time_limit_minutes": 25,
        "max_attempts": 2,
        "questions": [
            {
                "question_text": "What is the primary role of FastAPI Depends?",
                "order_index": 1,
                "points": 5,
                "options": [
                    {"option_text": "Dependency injection and authorization checks", "is_correct": True},
                    {"option_text": "Rendering HTML templates", "is_correct": False},
                    {"option_text": "Running background threads without asyncio", "is_correct": False},
                ]
            },
            {
                "question_text": "Which SQLAlchemy construct prevents Cartesian products in one-to-many?",
                "order_index": 2,
                "points": 5,
                "options": [
                    {"option_text": "selectinload or subqueryload", "is_correct": True},
                    {"option_text": "Cross join syntax", "is_correct": False},
                ]
            }
        ]
    }
    create_resp = client.post("/api/v1/instructor/courses/1/quizzes", headers=inst_headers, json=quiz_payload)
    assert create_resp.status_code == 201
    created_quiz = create_resp.json()
    quiz_id = created_quiz["id"]
    assert created_quiz["title"] == "Phase 4 Automated Assessment"
    assert created_quiz["is_published"] is False
    assert created_quiz["time_limit_minutes"] == 25
    assert created_quiz["max_attempts"] == 2
    assert len(created_quiz["questions"]) == 2

    # 2. Get quiz detail as instructor (preview with answer keys)
    detail_resp = client.get(f"/api/v1/instructor/quizzes/{quiz_id}", headers=inst_headers)
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["id"] == quiz_id
    # Answer keys MUST be visible to instructor
    assert any(opt["is_correct"] for opt in detail_data["questions"][0]["options"])

    # 3. Update quiz settings
    update_payload = {
        "title": "Phase 4 Updated Assessment Title",
        "passing_score": 75,
        "time_limit_minutes": 30,
        "max_attempts": 3,
    }
    upd_resp = client.put(f"/api/v1/instructor/quizzes/{quiz_id}", headers=inst_headers, json=update_payload)
    assert upd_resp.status_code == 200
    upd_data = upd_resp.json()
    assert upd_data["title"] == "Phase 4 Updated Assessment Title"
    assert upd_data["passing_score"] == 75
    assert upd_data["time_limit_minutes"] == 30
    assert upd_data["max_attempts"] == 3

    # 4. Toggle publish status
    pub_resp = client.patch(f"/api/v1/instructor/quizzes/{quiz_id}/publish", headers=inst_headers)
    assert pub_resp.status_code == 200
    assert pub_resp.json()["is_published"] is True

    # 5. Delete quiz safely
    del_resp = client.delete(f"/api/v1/instructor/quizzes/{quiz_id}", headers=inst_headers)
    assert del_resp.status_code == 200


def test_student_quiz_attempt_limits(client):
    inst_token = get_auth_token(client, "sarah.chen@eduverse.io")
    inst_headers = {"Authorization": f"Bearer {inst_token}"}
    student_token = get_auth_token(client, "alex.rivera@eduverse.io")
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # 1. Create a quiz with max_attempts = 1
    quiz_payload = {
        "title": "Strict Single Attempt Exam",
        "description": "Final assessment with strictly one attempt allowed.",
        "passing_score": 70,
        "is_published": True,
        "time_limit_minutes": 10,
        "max_attempts": 1,
        "questions": [
            {
                "question_text": "Is SQLite embedded?",
                "order_index": 1,
                "points": 1,
                "options": [
                    {"option_text": "Yes, it is serverless and embedded", "is_correct": True},
                    {"option_text": "No, it requires a dedicated daemon process", "is_correct": False},
                ]
            }
        ]
    }
    create_resp = client.post("/api/v1/instructor/courses/1/quizzes", headers=inst_headers, json=quiz_payload)
    assert create_resp.status_code == 201
    quiz_id = create_resp.json()["id"]

    # 2. Student starts attempt 1
    start_resp1 = client.post(f"/api/v1/quizzes/{quiz_id}/start", headers=student_headers)
    assert start_resp1.status_code == 200
    attempt1_id = start_resp1.json()["attempt_id"]

    # 3. Student submits attempt 1
    sub_resp1 = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        headers=student_headers,
        json={"attempt_id": attempt1_id, "answers": {}}
    )
    assert sub_resp1.status_code == 200

    # 4. Student tries to start attempt 2 -> MUST be rejected (max attempts reached)
    start_resp2 = client.post(f"/api/v1/quizzes/{quiz_id}/start", headers=student_headers)
    assert start_resp2.status_code == 400
    assert "maximum" in start_resp2.json()["detail"].lower()

    # 5. Student tries to submit without attempt_id -> MUST be rejected (max attempts reached)
    sub_resp2 = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        headers=student_headers,
        json={"answers": {}}
    )
    assert sub_resp2.status_code == 400
    assert "maximum" in sub_resp2.json()["detail"].lower()


def test_student_quiz_start_session_and_timer(client):
    inst_token = get_auth_token(client, "sarah.chen@eduverse.io")
    inst_headers = {"Authorization": f"Bearer {inst_token}"}
    student_token = get_auth_token(client, "alex.rivera@eduverse.io")
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # Create timed quiz
    quiz_payload = {
        "title": "Timed Assessment Check",
        "description": "Test timer response format",
        "passing_score": 60,
        "is_published": True,
        "time_limit_minutes": 20,
        "max_attempts": 3,
        "questions": [
            {
                "question_text": "What does HTTP status 200 represent?",
                "order_index": 1,
                "points": 2,
                "options": [
                    {"option_text": "OK - Success", "is_correct": True},
                    {"option_text": "Not Found", "is_correct": False},
                ]
            }
        ]
    }
    create_resp = client.post("/api/v1/instructor/courses/1/quizzes", headers=inst_headers, json=quiz_payload)
    assert create_resp.status_code == 201
    quiz_id = create_resp.json()["id"]

    # Start session
    start_resp = client.post(f"/api/v1/quizzes/{quiz_id}/start", headers=student_headers)
    assert start_resp.status_code == 200
    start_data = start_resp.json()
    assert "attempt_id" in start_data
    assert start_data["time_limit_minutes"] == 20
    assert start_data["started_at"] is not None
    assert start_data["expires_at"] is not None
    attempt_id = start_data["attempt_id"]

    # Submit with attempt_id
    sub_resp = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        headers=student_headers,
        json={"attempt_id": attempt_id, "answers": {}}
    )
    assert sub_resp.status_code == 200
    result_data = sub_resp.json()
    assert result_data["attempt_id"] == attempt_id

    # Trying to re-submit same attempt MUST be rejected
    resub_resp = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        headers=student_headers,
        json={"attempt_id": attempt_id, "answers": {}}
    )
    assert resub_resp.status_code == 400
    assert "already" in resub_resp.json()["detail"].lower()


def test_draft_quiz_privacy_and_access_control(client):
    inst_token = get_auth_token(client, "sarah.chen@eduverse.io")
    inst_headers = {"Authorization": f"Bearer {inst_token}"}
    student_token = get_auth_token(client, "alex.rivera@eduverse.io")
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # Create draft quiz (is_published=False)
    quiz_payload = {
        "title": "Unpublished Draft Exam",
        "description": "Instructor is currently drafting this.",
        "passing_score": 80,
        "is_published": False,
        "questions": [
            {
                "question_text": "Sample draft question",
                "order_index": 1,
                "points": 1,
                "options": [
                    {"option_text": "Correct draft answer", "is_correct": True},
                    {"option_text": "Incorrect draft answer", "is_correct": False},
                ]
            }
        ]
    }
    create_resp = client.post("/api/v1/instructor/courses/1/quizzes", headers=inst_headers, json=quiz_payload)
    assert create_resp.status_code == 201
    quiz_id = create_resp.json()["id"]

    # Student cannot view draft quiz
    get_resp = client.get(f"/api/v1/quizzes/{quiz_id}", headers=student_headers)
    assert get_resp.status_code == 403
    assert "draft" in get_resp.json()["detail"].lower()

    # Student cannot start draft quiz
    start_resp = client.post(f"/api/v1/quizzes/{quiz_id}/start", headers=student_headers)
    assert start_resp.status_code == 403

    # Student cannot submit draft quiz
    sub_resp = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        headers=student_headers,
        json={"answers": {}}
    )
    assert sub_resp.status_code == 403


def test_quiz_attempt_privacy_isolation(client):
    student1_token = get_auth_token(client, "alex.rivera@eduverse.io")
    student1_headers = {"Authorization": f"Bearer {student1_token}"}
    student2_token = get_auth_token(client, "priya.patel@eduverse.io")
    student2_headers = {"Authorization": f"Bearer {student2_token}"}
    inst_token = get_auth_token(client, "sarah.chen@eduverse.io")
    inst_headers = {"Authorization": f"Bearer {inst_token}"}

    # Student 1 submits quiz 1
    sub_resp = client.post(
        "/api/v1/quizzes/1/submit",
        headers=student1_headers,
        json={"answers": {}}
    )
    assert sub_resp.status_code == 200
    attempt_id = sub_resp.json()["id"]

    # Student 1 can view their own attempt
    resp1 = client.get(f"/api/v1/quizzes/attempts/{attempt_id}", headers=student1_headers)
    assert resp1.status_code == 200

    # Student 2 CANNOT view Student 1's attempt
    resp2 = client.get(f"/api/v1/quizzes/attempts/{attempt_id}", headers=student2_headers)
    assert resp2.status_code == 403

    # Instructor for the course CAN view the attempt
    resp_inst = client.get(f"/api/v1/quizzes/attempts/{attempt_id}", headers=inst_headers)
    assert resp_inst.status_code == 200
