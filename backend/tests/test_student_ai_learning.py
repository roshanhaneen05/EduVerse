from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from app.database import SessionLocal
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson, LessonProgress
from app.models.quiz import Quiz, QuizAttempt
from app.models.section import CourseSection
from app.models.user import User


def _token(client, email: str, password: str = "EduVerseDemo2026!") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_enrolled_course(student_email: str, *, lesson_count: int = 1) -> dict:
    db = SessionLocal()
    try:
        student = db.query(User).filter(User.email == student_email).one()
        instructor = db.query(User).filter(User.role == "instructor").first()
        assert instructor is not None
        suffix = uuid4().hex[:12]
        course = Course(
            title=f"AI Learning Test {suffix}",
            description="A course used to verify student AI learning tools.",
            category="Testing",
            difficulty="Beginner",
            instructor_id=instructor.id,
            is_published=True,
        )
        db.add(course)
        db.flush()
        section = CourseSection(course_id=course.id, title="Foundations", order_index=1)
        db.add(section)
        db.flush()
        lessons = []
        for index in range(lesson_count):
            lesson = Lesson(
                course_id=course.id,
                section_id=section.id,
                title=f"Lesson {index + 1}",
                content=(
                    "Python lists preserve insertion order and allow indexed access. "
                    "The append operation adds an item to the end of a list."
                ),
                order_index=index + 1,
            )
            db.add(lesson)
            lessons.append(lesson)
        db.add(
            CourseEnrollment(
                student_id=student.id,
                course_id=course.id,
                status="approved",
            )
        )
        db.commit()
        return {
            "course_id": course.id,
            "section_id": section.id,
            "lesson_ids": [lesson.id for lesson in lessons],
            "student_id": student.id,
        }
    finally:
        db.close()


def _create_student(client) -> tuple[str, str]:
    email = f"ai-tools-{uuid4().hex[:12]}@eduverse.io"
    password = "StrongPassword123!"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "AI Tools Student"},
    )
    assert response.status_code == 201
    return email, password


def _generated_questions():
    questions = []
    answers = ("A", "B", "C", "D")
    for index, correct in enumerate(answers, start=1):
        options = [{"text": letter} for letter in answers]
        questions.append(
            {
                "question": f"Which option represents supported list fact {index}?",
                "question_type": "mcq",
                "options": options,
                "correct_answer": correct,
                "explanation": "The lesson states that Python lists preserve order and support indexed access.",
                "difficulty": "medium",
            }
        )
    questions.append(
        {
            "question": "What does append do to a Python list?",
            "question_type": "short_answer",
            "options": [],
            "correct_answer": "It adds an item to the end of the list.",
            "explanation": "The lesson describes append as adding an item at the end.",
            "difficulty": "medium",
        }
    )
    return {"questions": questions}


def test_ai_quiz_generation_scoring_history_and_student_isolation(client, monkeypatch):
    import app.services.ai_quiz_service as quiz_service

    email, password = _create_student(client)
    course = _create_enrolled_course(email)
    token = _token(client, email, password)
    headers = {"Authorization": f"Bearer {token}"}
    seen_payloads = []

    def fake_ai(prompt, payload):
        seen_payloads.append(payload)
        if prompt.startswith("Grade this short response"):
            return {"score": 0.75, "feedback": "Correct core idea; add that the list is ordered."}
        return _generated_questions()

    monkeypatch.setattr(quiz_service, "request_structured_ai_json", fake_ai)
    response = client.post(
        "/api/v1/student/ai-learning/quizzes",
        headers=headers,
        json={
            "course_id": course["course_id"],
            "lesson_id": course["lesson_ids"][0],
            "difficulty": "medium",
            "question_count": 5,
            "question_type": "mixed",
        },
    )
    assert response.status_code == 201, response.text
    quiz = response.json()
    assert len(quiz["questions"]) == 5
    assert "correct_answer" not in str(quiz)
    assert seen_payloads[0]["source_lessons"][0]["content"].startswith("Python lists preserve")

    started = client.post(
        f"/api/v1/student/ai-learning/quizzes/{quiz['quiz']['id']}/attempts",
        headers=headers,
        json={},
    )
    assert started.status_code == 201
    answers = []
    for index, question in enumerate(quiz["questions"]):
        if question["question_type"] == "short_answer":
            answers.append({"question_id": question["id"], "answer_text": "Append adds an item at the end."})
        else:
            answer_index = (index + 1) % len(question["options"]) if index == 3 else index
            selected = question["options"][answer_index]["id"]
            answers.append({"question_id": question["id"], "selected_option_id": selected})
    result = client.post(
        f"/api/v1/student/ai-learning/attempts/{started.json()['attempt_id']}/submit",
        headers=headers,
        json={"answers": answers},
    )
    assert result.status_code == 200, result.text
    result_data = result.json()
    assert result_data["total_points"] == 5
    assert result_data["percentage"] == 75
    assert result_data["answers"][-1]["automated_evaluation"] is True
    assert result_data["answers"][-1]["automated_feedback"]

    history = client.get("/api/v1/student/ai-learning/quizzes/history", headers=headers)
    assert history.status_code == 200
    assert history.json()[0]["attempt_id"] == result_data["id"]
    assert history.json()[0]["time_taken_seconds"] is not None

    other_email, other_password = _create_student(client)
    other_headers = {"Authorization": f"Bearer {_token(client, other_email, other_password)}"}
    private_attempt = client.get(
        f"/api/v1/student/ai-learning/attempts/{result_data['id']}",
        headers=other_headers,
    )
    assert private_attempt.status_code == 404
    private_history = client.get("/api/v1/student/ai-learning/quizzes/history", headers=other_headers)
    assert private_history.status_code == 200
    assert private_history.json() == []


def test_ai_quiz_requires_provider_and_rejects_non_enrolled_content(client, monkeypatch):
    import app.services.ai_quiz_service as quiz_service
    from app.services.structured_ai import AIProviderNotConfigured

    email, password = _create_student(client)
    course = _create_enrolled_course(email)
    token = _token(client, email, password)
    headers = {"Authorization": f"Bearer {token}"}

    def unavailable(*_args, **_kwargs):
        raise AIProviderNotConfigured("AI provider is not configured.")

    monkeypatch.setattr(quiz_service, "request_structured_ai_json", unavailable)
    request = {
        "course_id": course["course_id"],
        "lesson_id": course["lesson_ids"][0],
        "difficulty": "easy",
        "question_count": 5,
        "question_type": "mcq",
    }
    unavailable_response = client.post("/api/v1/student/ai-learning/quizzes", headers=headers, json=request)
    assert unavailable_response.status_code == 503

    outsider_email, outsider_password = _create_student(client)
    outsider_headers = {"Authorization": f"Bearer {_token(client, outsider_email, outsider_password)}"}
    forbidden = client.post("/api/v1/student/ai-learning/quizzes", headers=outsider_headers, json=request)
    assert forbidden.status_code == 403
    instructor_token = _token(client, "sarah.chen@eduverse.io")
    instructor_response = client.get(
        "/api/v1/student/ai-learning/courses",
        headers={"Authorization": f"Bearer {instructor_token}"},
    )
    assert instructor_response.status_code == 403


def test_study_plan_uses_real_progress_and_supports_task_actions(client, monkeypatch):
    import app.services.study_planner_service as planner_service

    email, password = _create_student(client)
    course = _create_enrolled_course(email, lesson_count=3)
    db = SessionLocal()
    try:
        completed_lesson_id = course["lesson_ids"][0]
        db.add(
            LessonProgress(
                student_id=course["student_id"],
                lesson_id=completed_lesson_id,
                is_completed=True,
                completed_at=datetime.now(timezone.utc),
            )
        )
        instructor_quiz = Quiz(
            course_id=course["course_id"],
            title="Low score signal",
            passing_score=70,
            is_published=True,
        )
        db.add(instructor_quiz)
        db.flush()
        db.add(
            QuizAttempt(
                quiz_id=instructor_quiz.id,
                student_id=course["student_id"],
                score=30,
                total_points=100,
                passed=False,
                is_completed=True,
            )
        )
        db.commit()
    finally:
        db.close()

    pending_lesson_ids = course["lesson_ids"][1:]
    captured_payloads = []

    def fake_planner(prompt, payload):
        captured_payloads.append(payload)
        return {
            "tasks": [
                {
                    "lesson_id": pending_lesson_ids[0],
                    "duration_minutes": 30,
                    "priority": "high",
                    "rationale": "This lesson is unfinished in the selected course.",
                },
                {
                    "lesson_id": pending_lesson_ids[1],
                    "duration_minutes": 30,
                    "priority": "medium",
                    "rationale": "This lesson also remains unfinished in the selected course.",
                },
            ],
            "recommendations": ["Complete the remaining lesson in this course before your target date."],
        }

    monkeypatch.setattr(planner_service, "request_structured_ai_json", fake_planner)
    token = _token(client, email, password)
    headers = {"Authorization": f"Bearer {token}"}
    target_date = (date.today() + timedelta(days=14)).isoformat()
    deadline_at = datetime.now(timezone.utc) + timedelta(days=5)
    request = {
        "course_ids": [course["course_id"]],
        "available_hours_per_day": 2,
        "preferred_time": "morning",
        "time_zone": "America/Los_Angeles",
        "daily_duration_minutes": 45,
        "target_completion_date": target_date,
        "deadlines": [
            {
                "course_id": course["course_id"],
                "title": "Python lists exam",
                "deadline_type": "exam",
                "due_at": deadline_at.isoformat(),
            }
        ],
    }
    saved_preferences = client.put(
        "/api/v1/student/ai-learning/planner/preferences",
        headers=headers,
        json=request,
    )
    assert saved_preferences.status_code == 200, saved_preferences.text
    assert saved_preferences.json()["deadlines"][0]["title"] == "Python lists exam"
    generated = client.post("/api/v1/student/ai-learning/planner/generate", headers=headers, json=request)
    assert generated.status_code == 201, generated.text
    planner = generated.json()
    assert len(planner["tasks"]) == 2
    task = planner["tasks"][0]
    assert {item["lesson_id"] for item in planner["tasks"]} == set(pending_lesson_ids)
    assert planner["course_progress"][0]["completed_lessons"] == 1
    assert planner["course_progress"][0]["total_lessons"] == 3
    assert {item["id"] for item in captured_payloads[0]["pending_lessons"]} == set(pending_lesson_ids)
    assert planner["course_progress"][0]["completion_percentage"] == 33.3
    assert "average_quiz_score" in captured_payloads[0]["course_progress"][0]
    assert captured_payloads[0]["course_progress"][0]["average_quiz_score"] == 30
    assert planner["recommendations"] == [
        "Complete the remaining lesson in this course before your target date."
    ]
    assert planner["reminders"]
    assert task["start_time"].startswith(("07:", "08:", "09:", "10:", "11:"))
    assert planner["tasks"][0]["scheduled_at"] != planner["tasks"][1]["scheduled_at"]
    assert planner["deadlines"][0]["title"] == "Python lists exam"

    overlap_response = client.put(
        f"/api/v1/student/ai-learning/planner/tasks/{task['id']}/schedule",
        headers=headers,
        json={"scheduled_at": planner["tasks"][1]["scheduled_at"]},
    )
    assert overlap_response.status_code == 409

    new_start = datetime.now(timezone.utc) + timedelta(days=2)
    new_start = new_start.replace(hour=17, minute=0, second=0, microsecond=0)
    moved = client.put(
        f"/api/v1/student/ai-learning/planner/tasks/{task['id']}/schedule",
        headers=headers,
        json={"scheduled_at": new_start.isoformat()},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["status"] == "pending"

    other_email, other_password = _create_student(client)
    other_headers = {"Authorization": f"Bearer {_token(client, other_email, other_password)}"}
    isolated = client.get("/api/v1/student/ai-learning/planner", headers=other_headers)
    assert isolated.status_code == 200
    assert isolated.json()["tasks"] == []
    forbidden_task = client.patch(
        f"/api/v1/student/ai-learning/planner/tasks/{task['id']}",
        headers=other_headers,
        json={"status": "completed"},
    )
    assert forbidden_task.status_code == 404

    completed = client.patch(
        f"/api/v1/student/ai-learning/planner/tasks/{task['id']}",
        headers=headers,
        json={"status": "completed"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    removed = client.delete(
        f"/api/v1/student/ai-learning/planner/tasks/{task['id']}",
        headers=headers,
    )
    assert removed.status_code == 204
