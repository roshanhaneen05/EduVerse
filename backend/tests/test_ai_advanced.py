import pytest
from fastapi.testclient import TestClient


def get_auth_token(client: TestClient, email: str, password: str = "EduVerseDemo2026!") -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestAdvancedAILearningAssistant:
    def test_course_and_lesson_grounded_chat(self, client: TestClient):
        alex_token = get_auth_token(client, "alex.rivera@eduverse.io")

        # Dynamically retrieve Alex's enrolled course and first lesson
        my_courses = client.get("/api/v1/student/my-learning", headers=auth_header(alex_token)).json()
        assert len(my_courses) > 0
        enrolled_course_id = my_courses[0]["course_id"]

        course_detail = client.get(f"/api/v1/courses/{enrolled_course_id}", headers=auth_header(alex_token)).json()
        assert len(course_detail["lessons"]) > 0
        lesson = course_detail["lessons"][0]
        lesson_id = lesson["id"]

        # 1. Ask a question grounded in the lesson
        payload = {
            "message": "Explain the architectural goals discussed in this lesson",
            "course_id": enrolled_course_id,
            "lesson_id": lesson_id,
        }
        res = client.post("/api/v1/ai/chat", json=payload, headers=auth_header(alex_token))
        assert res.status_code == 200
        data = res.json()
        assert data["is_course_grounded"] is True
        assert data["grounded_in"] is not None
        assert "Lesson:" in data["grounded_in"]
        assert len(data["message"]) > 0

        # 2. Ask an unrelated question with lesson context (should not invent facts)
        payload_unrelated = {
            "message": "What is the boiling point of liquid nitrogen?",
            "course_id": enrolled_course_id,
            "lesson_id": lesson_id,
        }
        res_unrelated = client.post("/api/v1/ai/chat", json=payload_unrelated, headers=auth_header(alex_token))
        assert res_unrelated.status_code == 200
        data_unrelated = res_unrelated.json()
        assert data_unrelated["is_course_grounded"] is False
        assert (
            "does not directly discuss this topic" in data_unrelated["message"].lower()
            or "knowledge base" in data_unrelated["message"].lower()
        )

    def test_unenrolled_student_access_blocked(self, client: TestClient):
        # Register a fresh unenrolled student
        client.cookies.clear()
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": "ai.unenrolled.student@eduverse.io", "password": "EduVerseDemo2026!", "full_name": "AI Unenrolled Student"},
        )
        assert reg.status_code in (201, 409)
        unenrolled_token = get_auth_token(client, "ai.unenrolled.student@eduverse.io")

        # Attempt to use AI with Course 1 (which this new student is not enrolled in)
        res_chat = client.post(
            "/api/v1/ai/chat",
            json={"message": "Summarize this course", "course_id": 1},
            headers=auth_header(unenrolled_token),
        )
        assert res_chat.status_code == 403

        # Attempt to summarize lesson from Course 1
        res_sum = client.post(
            "/api/v1/ai/lessons/1/summarize",
            headers=auth_header(unenrolled_token),
        )
        assert res_sum.status_code == 403

        # Attempt to generate practice questions for lesson from Course 1
        res_pq = client.post(
            "/api/v1/ai/lessons/1/practice-questions",
            headers=auth_header(unenrolled_token),
        )
        assert res_pq.status_code == 403

    def test_lesson_summarization(self, client: TestClient):
        alex_token = get_auth_token(client, "alex.rivera@eduverse.io")

        my_courses = client.get("/api/v1/student/my-learning", headers=auth_header(alex_token)).json()
        enrolled_course_id = my_courses[0]["course_id"]
        course_detail = client.get(f"/api/v1/courses/{enrolled_course_id}", headers=auth_header(alex_token)).json()
        lesson_id = course_detail["lessons"][0]["id"]

        # Summarize lesson
        res = client.post(
            f"/api/v1/ai/lessons/{lesson_id}/summarize",
            headers=auth_header(alex_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert data["lesson_id"] == lesson_id
        assert len(data["summary"]) > 30
        assert len(data["key_takeaways"]) >= 1
        assert data["word_count"] >= 10
        assert "Summary:" in data["summary"]

    def test_lesson_summarization_empty_content_handled(self, client: TestClient):
        sarah_token = get_auth_token(client, "sarah.chen@eduverse.io")

        # Create a lesson with fewer than 10 words (passing schema length >= 10 chars, but < 10 words)
        res_create = client.post(
            "/api/v1/instructor/courses/1/lessons",
            json={"title": "Empty Stub Lesson", "content": "Short text with only seven words now", "order_index": 99},
            headers=auth_header(sarah_token),
        )
        assert res_create.status_code == 201
        empty_lesson_id = res_create.json()["id"]

        # Attempting to summarize content with < 10 words should return 400 Bad Request
        res_sum = client.post(
            f"/api/v1/ai/lessons/{empty_lesson_id}/summarize",
            headers=auth_header(sarah_token),
        )
        assert res_sum.status_code == 400
        assert "too brief" in res_sum.json()["detail"].lower()

    def test_practice_questions_generation_and_validation(self, client: TestClient):
        alex_token = get_auth_token(client, "alex.rivera@eduverse.io")

        my_courses = client.get("/api/v1/student/my-learning", headers=auth_header(alex_token)).json()
        enrolled_course_id = my_courses[0]["course_id"]
        course_detail = client.get(f"/api/v1/courses/{enrolled_course_id}", headers=auth_header(alex_token)).json()
        lesson_id = course_detail["lessons"][0]["id"]

        res = client.post(
            f"/api/v1/ai/lessons/{lesson_id}/practice-questions",
            headers=auth_header(alex_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert data["lesson_id"] == lesson_id
        assert "questions" in data
        assert len(data["questions"]) == 3

        for q in data["questions"]:
            assert "id" in q
            assert len(q["question"]) > 10
            assert len(q["options"]) == 4
            assert 0 <= q["correct_index"] <= 3
            assert len(q["explanation"]) > 10
            assert len(q["concept_tested"]) > 3

    def test_personalized_study_recommendations(self, client: TestClient):
        alex_token = get_auth_token(client, "alex.rivera@eduverse.io")

        res = client.get(
            "/api/v1/ai/study-recommendations",
            headers=auth_header(alex_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert "recommendations" in data
        assert "total_recommendations" in data
        assert "advisory_notice" in data
        assert isinstance(data["recommendations"], list)
        assert data["total_recommendations"] == len(data["recommendations"])

        if data["total_recommendations"] > 0:
            rec = data["recommendations"][0]
            assert rec["type"] in ("continue_lesson", "review_quiz", "assignment_due", "take_quiz")
            assert rec["priority"] in ("urgent", "high", "medium", "low")
            assert len(rec["action_url"]) > 0
            assert len(rec["course_title"]) > 0

    def test_study_recommendations_unauthenticated_blocked(self, client: TestClient):
        client.cookies.clear()
        res = client.get("/api/v1/ai/study-recommendations")
        assert res.status_code == 401
