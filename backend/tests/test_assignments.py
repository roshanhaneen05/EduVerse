from datetime import datetime, timedelta, timezone
import pytest


def get_token(client, email: str, password: str = "EduVerseDemo2026!") -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


def test_assignment_creation_and_editing(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    headers = {"Authorization": f"Bearer {sarah_token}"}

    future_due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    # 1. Create assignment for course 1
    create_resp = client.post(
        "/api/v1/instructor/courses/1/assignments",
        json={
            "title": "Full-Stack Architecture Plan",
            "description": "Design modular architecture",
            "instructions": "Submit a markdown blueprint for the backend API and domain models.",
            "max_marks": 50,
            "due_date": future_due,
            "allow_resubmission": True,
            "is_published": False,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    assign_data = create_resp.json()
    assert assign_data["title"] == "Full-Stack Architecture Plan"
    assert assign_data["max_marks"] == 50
    assert assign_data["is_published"] is False
    assignment_id = assign_data["id"]

    # 2. Update assignment and publish
    update_resp = client.put(
        f"/api/v1/instructor/assignments/{assignment_id}",
        json={
            "title": "Full-Stack Architecture Plan (Final)",
            "max_marks": 60,
            "is_published": True,
        },
        headers=headers,
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["title"] == "Full-Stack Architecture Plan (Final)"
    assert updated_data["max_marks"] == 60
    assert updated_data["is_published"] is True

    # 3. List assignments for course as instructor
    list_resp = client.get("/api/v1/instructor/courses/1/assignments", headers=headers)
    assert list_resp.status_code == 200
    course_assignments = list_resp.json()
    assert any(a["id"] == assignment_id for a in course_assignments)


def test_instructor_ownership_restrictions(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    marcus_token = get_token(client, "marcus.vance@eduverse.io")

    # Sarah creates assignment in Course 1
    sarah_headers = {"Authorization": f"Bearer {sarah_token}"}
    assign = client.post(
        "/api/v1/instructor/courses/1/assignments",
        json={
            "title": "Sarah Exclusive Assignment",
            "instructions": "Only for course 1 students to complete.",
            "max_marks": 100,
        },
        headers=sarah_headers,
    ).json()

    # Marcus (instructor of course 2) attempts to edit Sarah's assignment -> 403 Forbidden
    marcus_headers = {"Authorization": f"Bearer {marcus_token}"}
    edit_resp = client.put(
        f"/api/v1/instructor/assignments/{assign['id']}",
        json={"title": "Marcus Hijack"},
        headers=marcus_headers,
    )
    assert edit_resp.status_code == 403

    # Marcus attempts to create assignment in Course 1 -> 403 Forbidden
    create_resp = client.post(
        "/api/v1/instructor/courses/1/assignments",
        json={"title": "Marcus Course 1 Attempt", "instructions": "Should fail immediately."},
        headers=marcus_headers,
    )
    assert create_resp.status_code == 403


def test_student_enrollment_and_access_restrictions(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    priya_token = get_token(client, "priya.patel@eduverse.io")  # Not enrolled in Course 1
    sarah_headers = {"Authorization": f"Bearer {sarah_token}"}
    priya_headers = {"Authorization": f"Bearer {priya_token}"}

    # Create published assignment in Course 1
    assign = client.post(
        "/api/v1/instructor/courses/1/assignments",
        json={
            "title": "Access Restriction Test",
            "instructions": "Demonstrating enrollment authorization boundaries.",
            "max_marks": 50,
            "is_published": True,
        },
        headers=sarah_headers,
    ).json()

    # Priya is NOT enrolled in course 1 -> Access forbidden (403)
    priya_list = client.get("/api/v1/assignments/course/1", headers=priya_headers)
    assert priya_list.status_code == 403

    priya_detail = client.get(f"/api/v1/assignments/{assign['id']}", headers=priya_headers)
    assert priya_detail.status_code == 403

    priya_submit = client.post(
        f"/api/v1/assignments/{assign['id']}/submit",
        json={"submission_text": "Unauthorized submission attempt"},
        headers=priya_headers,
    )
    assert priya_submit.status_code == 403


def test_submission_creation_resubmission_and_deadlines(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    alex_token = get_token(client, "alex.rivera@eduverse.io")  # Enrolled in Course 1
    sarah_headers = {"Authorization": f"Bearer {sarah_token}"}
    alex_headers = {"Authorization": f"Bearer {alex_token}"}

    # 1. Past due date assignment to test late flag
    past_due = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    assign_late = client.post(
        "/api/v1/instructor/courses/1/assignments",
        json={
            "title": "Late Flag Verification Assignment",
            "instructions": "Submit work to verify automatic late detection.",
            "max_marks": 100,
            "due_date": past_due,
            "is_published": True,
            "allow_resubmission": True,
        },
        headers=sarah_headers,
    ).json()

    sub_late_resp = client.post(
        f"/api/v1/assignments/{assign_late['id']}/submit",
        json={"submission_text": "Submitted after due date to test late detection."},
        headers=alex_headers,
    )
    assert sub_late_resp.status_code == 200
    assert sub_late_resp.json()["is_late"] is True

    # 2. Assignment with allow_resubmission = False
    assign_no_resub = client.post(
        "/api/v1/instructor/courses/1/assignments",
        json={
            "title": "Strict Single Submission Exam",
            "instructions": "Only one submission allowed per student.",
            "max_marks": 100,
            "is_published": True,
            "allow_resubmission": False,
        },
        headers=sarah_headers,
    ).json()

    # First submission -> 200 OK
    first_sub = client.post(
        f"/api/v1/assignments/{assign_no_resub['id']}/submit",
        json={"submission_text": "First attempt response."},
        headers=alex_headers,
    )
    assert first_sub.status_code == 200

    # Second submission attempt -> 400 Bad Request
    second_sub = client.post(
        f"/api/v1/assignments/{assign_no_resub['id']}/submit",
        json={"submission_text": "Second attempt that must be blocked."},
        headers=alex_headers,
    )
    assert second_sub.status_code == 400
    assert "Resubmissions are disabled" in second_sub.json()["detail"]

    # 3. Closed assignment blocks submissions
    client.patch(f"/api/v1/instructor/assignments/{assign_late['id']}/close", headers=sarah_headers)
    blocked_sub = client.post(
        f"/api/v1/assignments/{assign_late['id']}/submit",
        json={"submission_text": "Attempt to submit to closed assignment."},
        headers=alex_headers,
    )
    assert blocked_sub.status_code == 400
    assert "closed" in blocked_sub.json()["detail"]


def test_grading_workflow_and_validation(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    marcus_token = get_token(client, "marcus.vance@eduverse.io")
    alex_token = get_token(client, "alex.rivera@eduverse.io")
    sarah_headers = {"Authorization": f"Bearer {sarah_token}"}
    marcus_headers = {"Authorization": f"Bearer {marcus_token}"}
    alex_headers = {"Authorization": f"Bearer {alex_token}"}

    # Create published assignment with max 50 marks
    assign = client.post(
        "/api/v1/instructor/courses/1/assignments",
        json={
            "title": "Grading Protocol Assignment",
            "instructions": "Demonstrate grading, feedback, and score limits.",
            "max_marks": 50,
            "is_published": True,
        },
        headers=sarah_headers,
    ).json()

    # Alex submits work
    sub_resp = client.post(
        f"/api/v1/assignments/{assign['id']}/submit",
        json={"submission_text": "Alex Rivera's completed implementation and analysis."},
        headers=alex_headers,
    )
    assert sub_resp.status_code == 200
    submission_id = sub_resp.json()["id"]

    # Student cannot grade submission -> 403 Forbidden
    student_grade_attempt = client.put(
        f"/api/v1/instructor/submissions/{submission_id}/grade",
        json={"grade": 50, "feedback": "Self-awarded grade."},
        headers=alex_headers,
    )
    assert student_grade_attempt.status_code == 403

    # Student cannot access instructor submission rosters or another student's private submission -> 403 Forbidden
    student_roster_attempt = client.get(
        f"/api/v1/instructor/assignments/{assign['id']}/submissions",
        headers=alex_headers,
    )
    assert student_roster_attempt.status_code == 403

    student_sub_detail_attempt = client.get(
        f"/api/v1/instructor/submissions/{submission_id}",
        headers=alex_headers,
    )
    assert student_sub_detail_attempt.status_code == 403

    # Instructor from another course cannot grade this submission -> 403 Forbidden
    other_instructor_attempt = client.put(
        f"/api/v1/instructor/submissions/{submission_id}/grade",
        json={"grade": 40, "feedback": "Unauthorized instructor grading."},
        headers=marcus_headers,
    )
    assert other_instructor_attempt.status_code == 403

    # Grade boundary validation: negative grade -> 422 or 400
    neg_grade = client.put(
        f"/api/v1/instructor/submissions/{submission_id}/grade",
        json={"grade": -5.0, "feedback": "Negative marks."},
        headers=sarah_headers,
    )
    assert neg_grade.status_code in (400, 422)

    # Grade boundary validation: grade > max_marks (60 > 50) -> 400 Bad Request
    over_max = client.put(
        f"/api/v1/instructor/submissions/{submission_id}/grade",
        json={"grade": 60.0, "feedback": "Exceeds maximum marks."},
        headers=sarah_headers,
    )
    assert over_max.status_code == 400
    assert "between 0 and 50" in over_max.json()["detail"]

    # Valid grade award (45/50 with constructive feedback)
    valid_grade = client.put(
        f"/api/v1/instructor/submissions/{submission_id}/grade",
        json={
            "grade": 45.0,
            "feedback": "Outstanding architectural depth! Well structured domain models.",
        },
        headers=sarah_headers,
    )
    assert valid_grade.status_code == 200
    graded_data = valid_grade.json()
    assert graded_data["grade"] == 45.0
    assert graded_data["status"] == "graded"
    assert graded_data["feedback"] == "Outstanding architectural depth! Well structured domain models."
    assert graded_data["graded_by_id"] is not None
    assert graded_data["graded_at"] is not None

    # Student views awarded grade and feedback
    alex_view = client.get(f"/api/v1/assignments/{assign['id']}/my-submission", headers=alex_headers)
    assert alex_view.status_code == 200
    alex_sub = alex_view.json()
    assert alex_sub["grade"] == 45.0
    assert alex_sub["feedback"] == "Outstanding architectural depth! Well structured domain models."
    assert alex_sub["status"] == "graded"


def test_safe_assignment_deletion_and_archival(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    alex_token = get_token(client, "alex.rivera@eduverse.io")
    sarah_headers = {"Authorization": f"Bearer {sarah_token}"}
    alex_headers = {"Authorization": f"Bearer {alex_token}"}

    # 1. Assignment without submissions can be deleted directly
    assign_empty = client.post(
        "/api/v1/instructor/courses/1/assignments",
        json={"title": "Empty Assignment To Delete", "instructions": "No submissions will be made."},
        headers=sarah_headers,
    ).json()

    del_empty = client.delete(f"/api/v1/instructor/assignments/{assign_empty['id']}", headers=sarah_headers)
    assert del_empty.status_code == 200
    assert del_empty.json()["archived"] is False

    # 2. Assignment WITH student submissions
    assign_with_subs = client.post(
        "/api/v1/instructor/courses/1/assignments",
        json={
            "title": "Assignment With Submissions",
            "instructions": "Student will submit here.",
            "is_published": True,
        },
        headers=sarah_headers,
    ).json()

    client.post(
        f"/api/v1/assignments/{assign_with_subs['id']}/submit",
        json={"submission_text": "Vital student research project."},
        headers=alex_headers,
    )

    # Attempt to permanently delete without archive flag -> 400 Bad Request
    del_blocked = client.delete(f"/api/v1/instructor/assignments/{assign_with_subs['id']}", headers=sarah_headers)
    assert del_blocked.status_code == 400
    assert "contains student submissions" in del_blocked.json()["detail"]

    # Delete with archive_if_submissions=True -> Safely archived
    del_archived = client.delete(
        f"/api/v1/instructor/assignments/{assign_with_subs['id']}?archive_if_submissions=true",
        headers=sarah_headers,
    )
    assert del_archived.status_code == 200
    assert del_archived.json()["archived"] is True

    # Verify student submission is still preserved
    alex_check = client.get(f"/api/v1/assignments/{assign_with_subs['id']}/my-submission", headers=alex_headers)
    assert alex_check.status_code == 200
    assert alex_check.json()["submission_text"] == "Vital student research project."

