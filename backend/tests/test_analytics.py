import pytest
from app.services.analytics_service import _sanitize_csv_cell


def get_auth_token(client, email, password="EduVerseDemo2026!"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        return resp.json()["access_token"]
    # Fallback to test registration
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


def test_instructor_dashboard_analytics(client):
    token = get_auth_token(client, "sarah.chen@eduverse.io")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/instructor/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Core required fields
    assert "total_courses" in data
    assert "published_courses" in data
    assert "total_students_enrolled" in data
    assert "unique_students_count" in data
    assert "total_assignments" in data
    assert "total_assignment_submissions" in data
    assert "pending_grading_count" in data
    assert "total_quizzes" in data
    assert "total_quiz_attempts" in data
    assert "average_quiz_score" in data
    assert "average_student_progress" in data
    assert "completed_enrollments_count" in data
    assert "course_completion_rate" in data
    assert "recent_enrollments" in data
    assert "courses_overview" in data

    assert data["total_courses"] >= 1
    assert isinstance(data["courses_overview"], list)
    if data["courses_overview"]:
        c = data["courses_overview"][0]
        assert "course_id" in c
        assert "title" in c
        assert "student_count" in c
        assert "average_progress" in c


def test_course_level_analytics(client):
    token = get_auth_token(client, "sarah.chen@eduverse.io")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/instructor/courses/1/analytics", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["course_id"] == 1
    assert "course_title" in data
    assert "total_students" in data
    assert "total_lessons" in data
    assert "average_completion_percentage" in data
    assert "course_completion_rate" in data
    assert "total_assignments" in data
    assert "total_assignment_submissions" in data
    assert "pending_grading_count" in data
    assert "graded_submissions_count" in data
    assert "assignment_submission_rate" in data
    assert "total_quizzes" in data
    assert "total_quiz_attempts" in data
    assert "average_quiz_score" in data
    assert "quiz_pass_rate" in data
    assert "quizzes_breakdown" in data
    assert "assignments_breakdown" in data


def test_course_student_report(client):
    token = get_auth_token(client, "sarah.chen@eduverse.io")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/instructor/courses/1/student-report", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["course_id"] == 1
    assert "course_title" in data
    assert "total_students" in data
    assert "students" in data
    assert isinstance(data["students"], list)

    if data["students"]:
        s = data["students"][0]
        assert "student_id" in s
        assert "full_name" in s
        assert "email" in s
        assert "enrolled_at" in s
        assert "completion_percentage" in s
        assert "completed_lessons_count" in s
        assert "total_lessons_count" in s
        assert "assignments_submitted_count" in s
        assert "quizzes_taken_count" in s
        assert "status" in s
        assert s["status"] in ("Completed", "In Progress", "Needs Attention")
        assert "assistance_reasons" in s


def test_student_detailed_progress(client):
    token = get_auth_token(client, "sarah.chen@eduverse.io")
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch report to get an enrolled student ID (Alex Rivera is enrolled in Course 1)
    report_resp = client.get("/api/v1/instructor/courses/1/student-report", headers=headers)
    assert report_resp.status_code == 200
    students = report_resp.json()["students"]
    assert len(students) >= 1
    target_student_id = students[0]["student_id"]

    resp = client.get(
        f"/api/v1/instructor/courses/1/students/{target_student_id}/progress",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["student_id"] == target_student_id
    assert data["course_id"] == 1
    assert "lessons_progress" in data
    assert "assignment_submissions" in data
    assert "quiz_attempts" in data
    assert "completion_percentage" in data
    assert "status" in data


def test_student_report_csv_export(client):
    token = get_auth_token(client, "sarah.chen@eduverse.io")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/instructor/courses/1/student-report/csv", headers=headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert "filename=" in resp.headers.get("content-disposition", "")

    csv_text = resp.text
    assert "Student ID,Student Name,Email" in csv_text


def test_csv_formula_injection_prevention():
    # Dangerous formula characters must be prepended with a quote
    assert _sanitize_csv_cell("=1+1") == "'=1+1"
    assert _sanitize_csv_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert _sanitize_csv_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert _sanitize_csv_cell("-5+2") == "'-5+2"
    assert _sanitize_csv_cell("\tTabPrefix") == "'\tTabPrefix"
    assert _sanitize_csv_cell("\rReturnPrefix") == "'\rReturnPrefix"

    # Normal harmless text should remain unchanged
    assert _sanitize_csv_cell("Alex Rivera") == "Alex Rivera"
    assert _sanitize_csv_cell("alex.rivera@eduverse.io") == "alex.rivera@eduverse.io"
    assert _sanitize_csv_cell(85.5) == "85.5"
    assert _sanitize_csv_cell(None) == ""


def test_analytics_cross_instructor_isolation(client):
    # Marcus Vance is instructor for Course 2, not Course 1 (Dr. Sarah Chen owns Course 1)
    token_marcus = get_auth_token(client, "marcus.vance@eduverse.io")
    headers_marcus = {"Authorization": f"Bearer {token_marcus}"}

    # Marcus tries to view Course 1 analytics -> 403 Forbidden
    resp = client.get("/api/v1/instructor/courses/1/analytics", headers=headers_marcus)
    assert resp.status_code == 403

    # Marcus tries to view Course 1 student report -> 403 Forbidden
    resp_report = client.get("/api/v1/instructor/courses/1/student-report", headers=headers_marcus)
    assert resp_report.status_code == 403

    # Marcus tries to export Course 1 CSV -> 403 Forbidden
    resp_csv = client.get("/api/v1/instructor/courses/1/student-report/csv", headers=headers_marcus)
    assert resp_csv.status_code == 403


def test_student_blocked_from_instructor_analytics(client):
    token_student = get_auth_token(client, "alex.rivera@eduverse.io")
    headers_student = {"Authorization": f"Bearer {token_student}"}

    # Student cannot access instructor dashboard
    resp1 = client.get("/api/v1/instructor/dashboard", headers=headers_student)
    assert resp1.status_code == 403

    # Student cannot access course analytics
    resp2 = client.get("/api/v1/instructor/courses/1/analytics", headers=headers_student)
    assert resp2.status_code == 403

    # Student cannot access student report
    resp3 = client.get("/api/v1/instructor/courses/1/student-report", headers=headers_student)
    assert resp3.status_code == 403


def test_analytics_empty_course_and_missing_resources(client):
    token = get_auth_token(client, "sarah.chen@eduverse.io")
    headers = {"Authorization": f"Bearer {token}"}

    # Non-existent course
    resp_not_found = client.get("/api/v1/instructor/courses/99999/analytics", headers=headers)
    assert resp_not_found.status_code == 404

    # Non-existent student progress
    resp_student_not_found = client.get(
        "/api/v1/instructor/courses/1/students/99999/progress",
        headers=headers,
    )
    assert resp_student_not_found.status_code == 404

    # Create a fresh empty course owned by Sarah Chen
    create_course_resp = client.post(
        "/api/v1/instructor/courses",
        headers=headers,
        json={
            "title": "Empty Analytics Test Course",
            "category": "Testing",
            "difficulty": "Beginner",
            "description": "Brand new course with zero students or items."
        }
    )
    assert create_course_resp.status_code == 201
    empty_course_id = create_course_resp.json()["id"]

    # Access analytics for empty course: must return 200 with 0s and empty lists, never divide by zero
    empty_analytics_resp = client.get(
        f"/api/v1/instructor/courses/{empty_course_id}/analytics",
        headers=headers,
    )
    assert empty_analytics_resp.status_code == 200
    empty_data = empty_analytics_resp.json()
    assert empty_data["total_students"] == 0
    assert empty_data["course_completion_rate"] == 0.0
    assert empty_data["assignment_submission_rate"] == 0.0
    assert empty_data["average_quiz_score"] == 0.0
    assert empty_data["quizzes_breakdown"] == []
    assert empty_data["assignments_breakdown"] == []

    # Student report for empty course
    empty_report_resp = client.get(
        f"/api/v1/instructor/courses/{empty_course_id}/student-report",
        headers=headers,
    )
    assert empty_report_resp.status_code == 200
    assert empty_report_resp.json()["total_students"] == 0
    assert empty_report_resp.json()["students"] == []

    # Clean up created course
    client.delete(f"/api/v1/instructor/courses/{empty_course_id}", headers=headers)

