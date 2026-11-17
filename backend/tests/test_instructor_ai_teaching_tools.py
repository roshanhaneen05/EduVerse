import json
from uuid import uuid4

from app.database import SessionLocal
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson
from app.models.section import CourseSection
from app.models.user import User
from app.security.password import hash_password
from app.services.storage import get_storage_provider


def _login(client, email, password="EduVerseDemo2026!"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_test_context(client):
    instructor_email = "sarah.chen@eduverse.io"
    student_email = f"teaching-tools-{uuid4().hex[:12]}@eduverse.io"
    other_instructor_email = f"other-faculty-{uuid4().hex[:12]}@eduverse.io"
    password = "StrongPassword123!"
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": student_email, "password": password, "full_name": "Teaching Tools Student"},
    )
    assert registered.status_code == 201

    db = SessionLocal()
    try:
        instructor = db.query(User).filter(User.email == instructor_email).one()
        student = db.query(User).filter(User.email == student_email).one()
        other_instructor = User(
            full_name="Other Faculty",
            email=other_instructor_email,
            password_hash=hash_password(password),
            role="instructor",
        )
        db.add(other_instructor)
        suffix = uuid4().hex[:10]
        course = Course(
            title=f"Instructor AI Course {suffix}",
            description="Course created for instructor AI tool tests.",
            category="Testing",
            difficulty="Intermediate",
            instructor_id=instructor.id,
            is_published=True,
        )
        db.add(course)
        db.flush()
        section = CourseSection(course_id=course.id, title="Foundations", order_index=1)
        db.add(section)
        db.flush()
        lesson = Lesson(
            course_id=course.id,
            section_id=section.id,
            title="Service boundaries",
            order_index=1,
            content="A service boundary separates responsibilities. Services own domain behavior and coordinate persistence.",
        )
        assignment = Assignment(
            course_id=course.id,
            section_id=section.id,
            title="Explain service boundaries",
            description="Explain an architectural concept.",
            instructions="Explain what a service boundary is and why responsibilities should be separated.",
            max_marks=10,
            is_published=True,
        )
        db.add_all([lesson, assignment])
        db.add(CourseEnrollment(student_id=student.id, course_id=course.id, status="approved"))
        db.flush()
        submission = AssignmentSubmission(
            assignment_id=assignment.id,
            student_id=student.id,
            submission_text="A service boundary separates domain responsibilities and helps coordinate persistence.",
            status="submitted",
        )
        db.add(submission)
        db.commit()
        return {
            "course_id": course.id,
            "section_id": section.id,
            "lesson_id": lesson.id,
            "assignment_id": assignment.id,
            "submission_id": submission.id,
            "student_id": student.id,
            "instructor_headers": _login(client, instructor_email),
            "other_instructor_headers": _login(client, other_instructor_email, password),
            "student_headers": _login(client, student_email, password),
        }
    finally:
        db.close()


def _evaluation_response():
    return {
        "criteria": [
            {
                "criterion_name": "Concept accuracy",
                "maximum_marks": 6,
                "suggested_marks": 5,
                "feedback": "The core definition is accurate.",
            },
            {
                "criterion_name": "Completeness",
                "maximum_marks": 4,
                "suggested_marks": 3,
                "feedback": "One supporting detail is missing.",
            },
        ],
        "feedback": "The response identifies the core concept.",
        "missing_concepts": ["The submission could explain module boundaries."],
        "incorrect_explanations": [],
        "improvements": ["Add an example of a service coordinating persistence."],
    }


def test_ai_assignment_evaluation_stays_private_until_instructor_approval(client, monkeypatch):
    from app.services import instructor_ai_service

    context = _create_test_context(client)
    calls = []

    def fake_ai(prompt, payload):
        calls.append(payload)
        return _evaluation_response()

    monkeypatch.setattr(instructor_ai_service, "request_structured_ai_json", fake_ai)
    student_upload = client.post(
        f"/api/v1/assignments/{context['assignment_id']}/attachments",
        headers=context["student_headers"],
        files={"file": ("submission.txt", b"Additional service boundary example.", "text/plain")},
    )
    assert student_upload.status_code == 201, student_upload.text
    uploaded = student_upload.json()
    assert uploaded["name"] == "submission.txt"
    try:
        submission_response = client.post(
            f"/api/v1/assignments/{context['assignment_id']}/submit",
            headers=context["student_headers"],
            json={
                "submission_text": "The uploaded text gives an extra example.",
                "attachments_json": json.dumps([uploaded]),
            },
        )
        assert submission_response.status_code == 200, submission_response.text
        submission_id = submission_response.json()["id"]
        attachment_response = client.get(
            f"/api/v1/instructor/teaching/submissions/{submission_id}/attachments/0",
            headers=context["instructor_headers"],
        )
        assert attachment_response.status_code == 200
        assert attachment_response.content == b"Additional service boundary example."
        student_attachment_access = client.get(
            f"/api/v1/instructor/teaching/submissions/{submission_id}/attachments/0",
            headers=context["student_headers"],
        )
        assert student_attachment_access.status_code == 403

        forbidden = client.get(
            "/api/v1/instructor/teaching/courses",
            headers=context["student_headers"],
        )
        assert forbidden.status_code == 403

        rubric = client.put(
            f"/api/v1/instructor/teaching/assignments/{context['assignment_id']}/rubric",
            headers=context["instructor_headers"],
            json={
                "expected_answer": "A service boundary separates responsibilities.",
                "criteria": [
                    {
                        "criterion_name": "Concept accuracy",
                        "maximum_marks": 6,
                        "description": "Correct description of a service boundary.",
                        "guidelines": "Use the expected concept.",
                    },
                    {
                        "criterion_name": "Completeness",
                        "maximum_marks": 4,
                        "description": "Explain implications or provide an example.",
                        "guidelines": "",
                    },
                ],
            },
        )
        assert rubric.status_code == 200, rubric.text

        evaluated = client.post(
            f"/api/v1/instructor/teaching/submissions/{submission_id}/evaluate",
            headers=context["instructor_headers"],
        )
        assert evaluated.status_code == 200, evaluated.text
        evaluation = evaluated.json()
        assert evaluation["evaluation_status"] == "pending_review"
        assert evaluation["ai_suggested_marks"] == 8
        assert evaluation["final_marks"] is None
        assert "Additional service boundary example." in calls[0]["student_submission"]
        private_result = client.get(
            f"/api/v1/assignments/{context['assignment_id']}/my-submission",
            headers=context["student_headers"],
        )
        assert private_result.status_code == 200
        assert private_result.json()["grade"] is None

        edited = client.put(
            f"/api/v1/instructor/teaching/evaluations/{evaluation['id']}",
            headers=context["instructor_headers"],
            json={
                "final_marks": 7,
                "instructor_feedback": "Reviewed: add a concrete example.",
                "criteria": [
                    {
                        "id": criterion["id"],
                        "criterion_name": criterion["criterion_name"],
                        "maximum_marks": criterion["maximum_marks"],
                        "final_marks": marks,
                        "feedback": criterion["feedback"],
                    }
                    for criterion, marks in zip(evaluation["criteria"], (4, 3))
                ],
            },
        )
        assert edited.status_code == 200, edited.text
        approved = client.post(
            f"/api/v1/instructor/teaching/evaluations/{evaluation['id']}/approve",
            headers=context["instructor_headers"],
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["evaluation_status"] == "approved"
        student_result = client.get(
            f"/api/v1/assignments/{context['assignment_id']}/my-submission",
            headers=context["student_headers"],
        )
        assert student_result.status_code == 200
        assert student_result.json()["grade"] == 7
        assert student_result.json()["feedback"] == "Reviewed: add a concrete example."
    finally:
        get_storage_provider().delete_file(uploaded["storage_key"])


def test_ai_question_paper_draft_edit_publish_pdf_and_student_isolation(client, monkeypatch):
    from app.services import instructor_ai_service

    context = _create_test_context(client)
    calls = []
    generated = {
        "questions": [
            {
                "question_text": "What does a service boundary separate?",
                "question_type": "mcq",
                "difficulty": "medium",
                "marks": 5,
                "options": [
                    "Domain responsibilities",
                    "Only user interface colors",
                    "Database hardware",
                    "Course enrollment dates",
                ],
                "correct_answer": "Domain responsibilities",
                "explanation": "The lesson says service boundaries separate responsibilities.",
                "question_order": 1,
            },
            {
                "question_text": "Describe how a service coordinates persistence.",
                "question_type": "short_answer",
                "difficulty": "medium",
                "marks": 5,
                "options": [],
                "correct_answer": "It coordinates storage operations for domain behavior.",
                "explanation": "Answers should relate service behavior to persistence.",
                "question_order": 2,
            },
        ]
    }

    def fake_ai(prompt, payload):
        calls.append(payload)
        return generated

    monkeypatch.setattr(instructor_ai_service, "request_structured_ai_json", fake_ai)
    body = {
        "course_id": context["course_id"],
        "section_ids": [context["section_id"]],
        "lesson_ids": [context["lesson_id"]],
        "title": "Service Boundaries Assessment",
        "difficulty": "medium",
        "question_types": ["mcq", "short_answer"],
        "question_count": 2,
        "total_marks": 10,
        "duration_minutes": 45,
        "exam_date": None,
    }
    endpoint = "/api/v1/instructor/teaching/question-papers/generate"
    created = client.post(endpoint, headers=context["instructor_headers"], json=body)
    assert created.status_code == 201, created.text
    paper = created.json()
    assert paper["status"] == "draft"
    assert len(paper["questions"]) == 2
    assert "separates responsibilities" in calls[0]["source_lessons"][0]["content"]
    repeated = client.post(endpoint, headers=context["instructor_headers"], json=body)
    assert repeated.status_code == 201
    assert repeated.json()["id"] == paper["id"]
    assert len(calls) == 1

    edit_payload = {
        "title": paper["title"],
        "total_marks": 10,
        "duration_minutes": 60,
        "difficulty": "medium",
        "exam_date": None,
        "questions": [
            {**paper["questions"][0], "marks": 4, "question_order": 2},
            {**paper["questions"][1], "marks": 6, "question_order": 1},
        ],
    }
    saved = client.put(
        f"/api/v1/instructor/teaching/question-papers/{paper['id']}",
        headers=context["instructor_headers"],
        json=edit_payload,
    )
    assert saved.status_code == 200, saved.text
    assert [item["question_order"] for item in saved.json()["questions"]] == [1, 2]

    published = client.post(
        f"/api/v1/instructor/teaching/question-papers/{paper['id']}/publish",
        headers=context["instructor_headers"],
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    question_pdf = client.get(
        f"/api/v1/instructor/teaching/question-papers/{paper['id']}/pdf",
        headers=context["instructor_headers"],
    )
    answer_pdf = client.get(
        f"/api/v1/instructor/teaching/question-papers/{paper['id']}/answer-key.pdf",
        headers=context["instructor_headers"],
    )
    assert question_pdf.status_code == 200
    assert question_pdf.headers["content-type"] == "application/pdf"
    assert question_pdf.content.startswith(b"%PDF")
    assert answer_pdf.status_code == 200
    assert answer_pdf.content.startswith(b"%PDF")

    student_access = client.get(
        f"/api/v1/instructor/teaching/question-papers/{paper['id']}",
        headers=context["student_headers"],
    )
    assert student_access.status_code == 403
    cross_course_access = client.get(
        f"/api/v1/instructor/teaching/courses/{context['course_id']}/outline",
        headers=context["other_instructor_headers"],
    )
    assert cross_course_access.status_code == 403


def test_rubric_total_and_question_marks_are_validated(client, monkeypatch):
    from app.services import instructor_ai_service

    context = _create_test_context(client)
    invalid_rubric = client.put(
        f"/api/v1/instructor/teaching/assignments/{context['assignment_id']}/rubric",
        headers=context["instructor_headers"],
        json={
            "expected_answer": "Expected response.",
            "criteria": [
                {
                    "criterion_name": "Content",
                    "maximum_marks": 9,
                    "description": "Content correctness.",
                    "guidelines": "",
                }
            ],
        },
    )
    assert invalid_rubric.status_code == 422

    monkeypatch.setattr(
        instructor_ai_service,
        "request_structured_ai_json",
        lambda _prompt, _payload: {
            "questions": [
                {
                    "question_text": "Explain the service boundary concept.",
                    "question_type": "short_answer",
                    "difficulty": "medium",
                    "marks": 3,
                    "options": [],
                    "correct_answer": "It separates responsibilities.",
                    "explanation": "The lesson says it separates responsibilities.",
                    "question_order": 1,
                },
                {
                    "question_text": "How do services coordinate persistence?",
                    "question_type": "short_answer",
                    "difficulty": "medium",
                    "marks": 3,
                    "options": [],
                    "correct_answer": "They coordinate storage.",
                    "explanation": "The lesson says services coordinate persistence.",
                    "question_order": 2,
                },
            ]
        },
    )
    invalid_paper = client.post(
        "/api/v1/instructor/teaching/question-papers/generate",
        headers=context["instructor_headers"],
        json={
            "course_id": context["course_id"],
            "section_ids": [context["section_id"]],
            "lesson_ids": [context["lesson_id"]],
            "title": "Invalid paper",
            "difficulty": "medium",
            "question_types": ["short_answer"],
            "question_count": 2,
            "total_marks": 10,
            "duration_minutes": 30,
            "exam_date": None,
        },
    )
    assert invalid_paper.status_code == 502
    assert "do not add up" in invalid_paper.json()["detail"]
