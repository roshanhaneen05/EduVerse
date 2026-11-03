"""
End-to-End Verification Script for EduVerse Phase 2: Assignments & Grading.
Tests complete lifecycle using live API authentication and role authorization:
1. Instructor creates assignment.
2. Student views and submits assignment.
3. Instructor grades submission and provides feedback.
4. Student verifies grade and feedback.
5. Cleanup test assignment.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.assignment import Assignment, AssignmentSubmission

def run_e2e_verification():
    client = TestClient(app)
    print("=" * 60)
    print("STARTING END-TO-END VERIFICATION: ASSIGNMENTS & GRADING")
    print("=" * 60)

    # 1. Login as Instructor (Dr. Sarah Chen)
    print("\n[Step 1] Logging in as Instructor (sarah.chen@eduverse.io)...")
    res_inst = client.post("/api/v1/auth/login", json={
        "email": "sarah.chen@eduverse.io",
        "password": "EduVerseDemo2026!"
    })
    assert res_inst.status_code == 200, f"Instructor login failed: {res_inst.text}"
    sarah_token = res_inst.json()["access_token"]
    sarah_user = res_inst.json()["user"]
    print(f"  -> Logged in as: {sarah_user['full_name']} (Role: {sarah_user['role']}, ID: {sarah_user['id']})")
    sarah_headers = {"Authorization": f"Bearer {sarah_token}"}

    # 2. Login as Student (Alex Rivera)
    print("\n[Step 2] Logging in as Student (alex.rivera@eduverse.io)...")
    res_stud = client.post("/api/v1/auth/login", json={
        "email": "alex.rivera@eduverse.io",
        "password": "EduVerseDemo2026!"
    })
    assert res_stud.status_code == 200, f"Student login failed: {res_stud.text}"
    alex_token = res_stud.json()["access_token"]
    alex_user = res_stud.json()["user"]
    print(f"  -> Logged in as: {alex_user['full_name']} (Role: {alex_user['role']}, ID: {alex_user['id']})")
    alex_headers = {"Authorization": f"Bearer {alex_token}"}

    # 3. Instructor creates assignment for Course 1
    print("\n[Step 3] Instructor creates new published assignment in Course 1...")
    create_payload = {
        "title": "E2E Distributed Architecture Capstone",
        "description": "Comprehensive full-stack architecture design document",
        "instructions": "### Deliverables\n1. Component diagram\n2. API specifications\n3. Security threat model",
        "max_marks": 75,
        "is_published": True,
        "allow_resubmission": True
    }
    create_res = client.post("/api/v1/instructor/courses/1/assignments", json=create_payload, headers=sarah_headers)
    assert create_res.status_code == 201, f"Create assignment failed: {create_res.text}"
    assignment = create_res.json()
    assignment_id = assignment["id"]
    print(f"  -> Created Assignment ID {assignment_id}: '{assignment['title']}' (Max Marks: {assignment['max_marks']})")

    try:
        # 4. Student views assignments in Course 1
        print("\n[Step 4] Enrolled student views course assignments...")
        list_res = client.get("/api/v1/assignments/course/1", headers=alex_headers)
        assert list_res.status_code == 200, f"Student list assignments failed: {list_res.text}"
        found = [a for a in list_res.json() if a["id"] == assignment_id]
        assert len(found) == 1, "Created assignment not found in student list"
        print(f"  -> Student verified assignment visibility in course syllabus")

        # 5. Student views assignment detail
        detail_res = client.get(f"/api/v1/assignments/{assignment_id}", headers=alex_headers)
        assert detail_res.status_code == 200
        assert detail_res.json()["title"] == create_payload["title"]
        print(f"  -> Student fetched assignment detail successfully")

        # 6. Student submits written work
        print("\n[Step 5] Student submits written markdown solution...")
        submission_text = (
            "## Distributed Architecture Capstone\n\n"
            "### 1. API Architecture\n"
            "- FastAPI modular monolith with dependency injection\n"
            "- Argon2id password hashing and PyJWT tokens\n\n"
            "### 2. Threat Modeling\n"
            "- Server-side role validation on all endpoints\n"
            "- Parameterized SQLite / SQLAlchemy queries to prevent SQL injection"
        )
        sub_res = client.post(
            f"/api/v1/assignments/{assignment_id}/submit",
            json={"submission_text": submission_text},
            headers=alex_headers
        )
        assert sub_res.status_code == 200, f"Submission failed: {sub_res.text}"
        sub_data = sub_res.json()
        submission_id = sub_data["id"]
        assert sub_data["status"] == "submitted"
        assert sub_data["grade"] is None
        print(f"  -> Submission ID {submission_id} created with status '{sub_data['status']}'")

        # 7. Instructor views submissions roster
        print("\n[Step 6] Instructor retrieves submissions roster...")
        roster_res = client.get(f"/api/v1/instructor/assignments/{assignment_id}/submissions", headers=sarah_headers)
        assert roster_res.status_code == 200
        roster = roster_res.json()
        assert len(roster) >= 1
        alex_sub = [s for s in roster if s["id"] == submission_id][0]
        assert alex_sub["student"]["email"] == "alex.rivera@eduverse.io"
        print(f"  -> Instructor verified submission from {alex_sub['student']['full_name']}")

        # 8. Instructor grades the submission
        print("\n[Step 7] Instructor awards 71.5/75 marks and provides feedback...")
        grade_payload = {
            "grade": 71.5,
            "feedback": "Exemplary architectural rigor! The threat model and domain structures are exceptionally well articulated."
        }
        grade_res = client.put(
            f"/api/v1/instructor/submissions/{submission_id}/grade",
            json=grade_payload,
            headers=sarah_headers
        )
        assert grade_res.status_code == 200, f"Grading failed: {grade_res.text}"
        graded_data = grade_res.json()
        assert graded_data["status"] == "graded"
        assert graded_data["grade"] == 71.5
        assert graded_data["graded_by_id"] == sarah_user["id"]
        assert graded_data["graded_at"] is not None
        print(f"  -> Grade recorded: {graded_data['grade']}/75 (Status: {graded_data['status']}, Graded By: {sarah_user['full_name']})")

        # 9. Student checks their submission and grade
        print("\n[Step 8] Student views assessed grade and instructor feedback...")
        student_check_res = client.get(f"/api/v1/assignments/{assignment_id}/my-submission", headers=alex_headers)
        assert student_check_res.status_code == 200
        my_sub = student_check_res.json()
        assert my_sub["grade"] == 71.5
        assert my_sub["status"] == "graded"
        assert my_sub["feedback"] == grade_payload["feedback"]
        print(f"  -> Student verified Grade: {my_sub['grade']}/75")
        print(f"  -> Student verified Feedback: \"{my_sub['feedback']}\"")

        print("\n[SUCCESS] Entire End-to-End Workflow passed with 100% fidelity!")

    finally:
        # Cleanup: safely archive/delete the test assignment
        print("\n[Cleanup] Removing temporary test assignment...")
        del_res = client.delete(f"/api/v1/instructor/assignments/{assignment_id}?archive_if_submissions=true", headers=sarah_headers)
        print(f"  -> Test assignment cleaned up: {del_res.status_code}")
        # Remove from DB if needed
        db = SessionLocal()
        try:
            sub = db.query(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == assignment_id).first()
            if sub:
                db.delete(sub)
            asn = db.query(Assignment).filter(Assignment.id == assignment_id).first()
            if asn:
                db.delete(asn)
            db.commit()
            print("  -> Database restored to pristine pre-verification state.")
        finally:
            db.close()

if __name__ == "__main__":
    run_e2e_verification()
