from app.database import SessionLocal
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.user import User, UserRole
from sqlalchemy import func


def _token(client, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "EduVerseDemo2026!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_admin_analytics_endpoints_and_date_validation(client):
    admin_headers = {
        "Authorization": f"Bearer {_token(client, 'admin@eduverse.io')}"
    }
    student_headers = {
        "Authorization": f"Bearer {_token(client, 'alex.rivera@eduverse.io')}"
    }
    params = {"start_date": "2000-01-01", "end_date": "2099-12-31"}

    dashboard = client.get(
        "/api/v1/admin/analytics/dashboard", headers=admin_headers, params=params
    )
    assert dashboard.status_code == 200
    data = dashboard.json()

    db = SessionLocal()
    try:
        expected_students = db.query(func.count(User.id)).filter(
            User.role == UserRole.STUDENT.value
        ).scalar()
        expected_instructors = db.query(func.count(User.id)).filter(
            User.role == UserRole.INSTRUCTOR.value
        ).scalar()
        expected_published_courses = db.query(func.count(Course.id)).filter(
            Course.is_published.is_(True)
        ).scalar()
        expected_enrollments = db.query(func.count(CourseEnrollment.id)).scalar()
        expected_completed = db.query(func.count(CourseEnrollment.id)).filter(
            CourseEnrollment.completion_percentage >= 100
        ).scalar()

        assert data["overview"]["total_registered_students"] == expected_students
        assert data["overview"]["total_registered_instructors"] == expected_instructors
        assert data["overview"]["total_published_courses"] == expected_published_courses
        assert data["overview"]["total_enrollments"] == expected_enrollments
        assert data["overview"]["total_completed_courses"] == expected_completed
        for student in data["students"]["top_students"]:
            assert "email" not in student
        for activity in data["recent_activities"]:
            assert "email" not in activity
    finally:
        db.close()

    for section in ("overview", "students", "courses", "instructors", "trends", "activities"):
        response = client.get(
            f"/api/v1/admin/analytics/{section}",
            headers=admin_headers,
            params=params,
        )
        assert response.status_code == 200, section

    for endpoint in (
        "dashboard",
        "overview",
        "students",
        "courses",
        "instructors",
        "trends",
        "activities",
        "export",
    ):
        query = {**params, "format": "csv"} if endpoint == "export" else params
        response = client.get(
            f"/api/v1/admin/analytics/{endpoint}", headers=student_headers, params=query
        )
        assert response.status_code == 403

    invalid_range = client.get(
        "/api/v1/admin/analytics/dashboard",
        headers=admin_headers,
        params={"start_date": "2026-02-02", "end_date": "2026-02-01"},
    )
    assert invalid_range.status_code == 422
    partial_range = client.get(
        "/api/v1/admin/analytics/dashboard",
        headers=admin_headers,
        params={"start_date": "2026-02-01"},
    )
    assert partial_range.status_code == 422


def test_admin_analytics_csv_and_pdf_exports(client):
    headers = {"Authorization": f"Bearer {_token(client, 'admin@eduverse.io')}"}
    params = {
        "format": "csv",
        "start_date": "2000-01-01",
        "end_date": "2099-12-31",
    }
    csv_response = client.get(
        "/api/v1/admin/analytics/export", headers=headers, params=params
    )
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert "attachment" in csv_response.headers["content-disposition"]
    assert "Instructor" in csv_response.text

    params["format"] = "pdf"
    pdf_response = client.get(
        "/api/v1/admin/analytics/export", headers=headers, params=params
    )
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.content.startswith(b"%PDF-1.4")
