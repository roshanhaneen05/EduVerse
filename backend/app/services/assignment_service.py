from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.repositories.assignment_repository import (
    MongoAssignment,
    MongoAssignmentSubmission,
    count_submissions_stats_for_assignments,
    create_assignment_doc,
    create_submission_doc,
    delete_assignment_doc,
    delete_assignment_from_sqlite_shadow,
    delete_submission_doc,
    get_assignment_by_id,
    get_submission_by_assignment_and_student,
    get_submission_by_id,
    list_assignments_for_course,
    list_submissions_for_assignment,
    list_submissions_for_student_assignments,
    restore_assignment_snapshot,
    restore_submission_snapshot,
    sync_assignment_to_sqlite_shadow,
    sync_submission_to_sqlite_shadow,
    update_assignment_doc,
    update_submission_doc,
)
from app.repositories.course_repository import (
    MongoCourse,
    get_course_by_id,
    get_enrollment_by_student_and_course,
    get_section_by_id,
)
from app.repositories.user_repository import MongoUser, get_user_by_id, get_users_by_ids
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentDetailResponse,
    AssignmentResponse,
    AssignmentUpdate,
    StudentSummary,
    SubmissionCreate,
    SubmissionGradePayload,
    SubmissionResponse,
    SubmissionSummary,
)


def check_course_ownership(course: MongoCourse, user: MongoUser) -> None:
    """Ensure the user is the course instructor or an administrator."""
    if user.role != "admin" and course.instructor_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage assignments for this course.",
        )


def check_student_course_access(
    mongo_db: Database,
    course_id: int,
    user: MongoUser,
) -> MongoCourse:
    """Verify course exists and user is either enrolled, the course instructor, or an admin."""
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    if user.role != "admin" and course.instructor_id != user.id:
        enrollment = get_enrollment_by_student_and_course(mongo_db, user.id, course_id)
        if not enrollment or enrollment.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be enrolled in this course to access assignments.",
            )
    return course


def normalize_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure a datetime object is timezone-aware in UTC for safe comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _build_assignment_response(
    assignment: MongoAssignment,
    *,
    submission_count: int = 0,
    graded_count: int = 0,
    my_submission: Optional[SubmissionSummary] = None,
) -> AssignmentResponse:
    return AssignmentResponse(
        id=assignment.id,
        course_id=assignment.course_id,
        section_id=assignment.section_id,
        title=assignment.title,
        description=assignment.description,
        instructions=assignment.instructions,
        max_marks=assignment.max_marks,
        due_date=assignment.due_date,
        is_published=assignment.is_published,
        is_closed=assignment.is_closed,
        allow_resubmission=assignment.allow_resubmission,
        is_archived=assignment.is_archived,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
        submission_count=submission_count,
        graded_count=graded_count,
        my_submission=my_submission,
    )


def _to_submission_summary(sub: MongoAssignmentSubmission) -> SubmissionSummary:
    return SubmissionSummary(
        id=sub.id,
        student_id=sub.student_id,
        status=sub.status,
        submitted_at=sub.submitted_at,
        is_late=sub.is_late,
        grade=sub.grade,
        feedback=sub.feedback,
        graded_at=sub.graded_at,
    )


def _to_submission_response(
    sub: MongoAssignmentSubmission,
    *,
    student: Optional[MongoUser],
    assignment: MongoAssignment,
) -> SubmissionResponse:
    return SubmissionResponse(
        id=sub.id,
        assignment_id=sub.assignment_id,
        student_id=sub.student_id,
        student=(
            StudentSummary(id=student.id, full_name=student.full_name, email=student.email)
            if student
            else None
        ),
        submission_text=sub.submission_text,
        attachments_json=sub.attachments_json,
        status=sub.status,
        is_late=sub.is_late,
        submitted_at=sub.submitted_at,
        updated_at=sub.updated_at,
        grade=sub.grade,
        feedback=sub.feedback,
        graded_by_id=sub.graded_by_id,
        graded_at=sub.graded_at,
        assignment_title=assignment.title,
        max_marks=assignment.max_marks,
    )


# ---------------------------------------------------------------------------
# Instructor Service Operations
# ---------------------------------------------------------------------------


def create_assignment(
    mongo_db: Database,
    course_id: int,
    assignment_in: AssignmentCreate,
    current_user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> AssignmentResponse:
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    if assignment_in.section_id:
        sec = get_section_by_id(mongo_db, assignment_in.section_id)
        if not sec or sec.course_id != course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target section does not exist in this course.",
            )

    assignment = create_assignment_doc(
        mongo_db,
        course_id=course_id,
        section_id=assignment_in.section_id,
        title=assignment_in.title,
        description=assignment_in.description,
        instructions=assignment_in.instructions,
        max_marks=assignment_in.max_marks,
        due_date=assignment_in.due_date,
        is_published=assignment_in.is_published,
        allow_resubmission=assignment_in.allow_resubmission,
    )
    try:
        sync_assignment_to_sqlite_shadow(sqlite_db, assignment)
    except Exception:
        delete_assignment_doc(mongo_db, assignment.id)
        raise

    return _build_assignment_response(assignment)


def get_assignment_for_instructor(
    mongo_db: Database,
    assignment_id: int,
    current_user: MongoUser,
) -> AssignmentResponse:
    assignment = get_assignment_by_id(mongo_db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    course = get_course_by_id(mongo_db, assignment.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    sub_count, graded_count = count_submissions_stats_for_assignments(
        mongo_db, [assignment.id]
    ).get(assignment.id, (0, 0))
    return _build_assignment_response(
        assignment,
        submission_count=sub_count,
        graded_count=graded_count,
    )


def update_assignment(
    mongo_db: Database,
    assignment_id: int,
    assignment_in: AssignmentUpdate,
    current_user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> AssignmentResponse:
    assignment = get_assignment_by_id(mongo_db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    course = get_course_by_id(mongo_db, assignment.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    updates: dict = {}
    if assignment_in.title is not None:
        updates["title"] = assignment_in.title.strip()
    if assignment_in.description is not None:
        updates["description"] = assignment_in.description.strip() if assignment_in.description else None
    if assignment_in.instructions is not None:
        updates["instructions"] = assignment_in.instructions.strip()
    if assignment_in.max_marks is not None:
        updates["max_marks"] = assignment_in.max_marks
    if assignment_in.due_date is not None:
        updates["due_date"] = normalize_utc(assignment_in.due_date)
    if assignment_in.section_id is not None:
        if assignment_in.section_id > 0:
            sec = get_section_by_id(mongo_db, assignment_in.section_id)
            if not sec or sec.course_id != assignment.course_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Target section does not exist in this course.",
                )
            updates["section_id"] = assignment_in.section_id
        else:
            updates["section_id"] = None
    if assignment_in.allow_resubmission is not None:
        updates["allow_resubmission"] = assignment_in.allow_resubmission
    if assignment_in.is_published is not None:
        updates["is_published"] = assignment_in.is_published
    if assignment_in.is_closed is not None:
        updates["is_closed"] = assignment_in.is_closed
    if assignment_in.is_archived is not None:
        updates["is_archived"] = assignment_in.is_archived

    updated = update_assignment_doc(mongo_db, assignment.id, updates) if updates else assignment
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    try:
        sync_assignment_to_sqlite_shadow(sqlite_db, updated)
    except Exception:
        restore_assignment_snapshot(mongo_db, assignment)
        raise

    sub_count, graded_count = count_submissions_stats_for_assignments(
        mongo_db, [updated.id]
    ).get(updated.id, (0, 0))
    return _build_assignment_response(
        updated,
        submission_count=sub_count,
        graded_count=graded_count,
    )


def toggle_assignment_status(
    mongo_db: Database,
    assignment_id: int,
    attribute: str,
    current_user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> AssignmentResponse:
    assignment = get_assignment_by_id(mongo_db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    course = get_course_by_id(mongo_db, assignment.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    current_val = bool(getattr(assignment, attribute))
    updated = update_assignment_doc(mongo_db, assignment.id, {attribute: not current_val})
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    try:
        sync_assignment_to_sqlite_shadow(sqlite_db, updated)
    except Exception:
        restore_assignment_snapshot(mongo_db, assignment)
        raise

    sub_count, graded_count = count_submissions_stats_for_assignments(
        mongo_db, [updated.id]
    ).get(updated.id, (0, 0))
    return _build_assignment_response(
        updated,
        submission_count=sub_count,
        graded_count=graded_count,
    )


def delete_assignment(
    mongo_db: Database,
    assignment_id: int,
    current_user: MongoUser,
    archive_if_submissions: bool = False,
    sqlite_db: Optional[Session] = None,
) -> dict:
    assignment = get_assignment_by_id(mongo_db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    course = get_course_by_id(mongo_db, assignment.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    sub_count, _ = count_submissions_stats_for_assignments(
        mongo_db, [assignment.id]
    ).get(assignment.id, (0, 0))
    if sub_count > 0:
        if archive_if_submissions:
            updated = update_assignment_doc(
                mongo_db,
                assignment.id,
                {"is_archived": True, "is_published": False},
            )
            if updated:
                try:
                    sync_assignment_to_sqlite_shadow(sqlite_db, updated)
                except Exception:
                    restore_assignment_snapshot(mongo_db, assignment)
                    raise
            return {
                "message": "Assignment contains student submissions and has been safely archived.",
                "archived": True,
            }
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot permanently delete an assignment that contains student submissions. Archive it instead to preserve grading history.",
        )

    delete_assignment_doc(mongo_db, assignment_id)
    delete_assignment_from_sqlite_shadow(sqlite_db, assignment_id)
    return {"message": "Assignment successfully deleted.", "archived": False}


def list_instructor_assignments(
    mongo_db: Database,
    course_id: int,
    current_user: MongoUser,
) -> List[AssignmentResponse]:
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    assignments = list_assignments_for_course(
        mongo_db,
        course_id,
        published_only=False,
        exclude_archived=False,
        sort_asc=False,
    )
    stats = count_submissions_stats_for_assignments(mongo_db, [a.id for a in assignments])
    return [
        _build_assignment_response(
            a,
            submission_count=stats.get(a.id, (0, 0))[0],
            graded_count=stats.get(a.id, (0, 0))[1],
        )
        for a in assignments
    ]


def get_assignment_submissions_for_instructor(
    mongo_db: Database,
    assignment_id: int,
    current_user: MongoUser,
) -> List[SubmissionResponse]:
    assignment = get_assignment_by_id(mongo_db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    course = get_course_by_id(mongo_db, assignment.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    submissions = list_submissions_for_assignment(mongo_db, assignment_id)
    student_map = get_users_by_ids(mongo_db, [s.student_id for s in submissions])
    return [
        _to_submission_response(s, student=student_map.get(s.student_id), assignment=assignment)
        for s in submissions
    ]


def get_submission_detail_for_instructor(
    mongo_db: Database,
    submission_id: int,
    current_user: MongoUser,
) -> SubmissionResponse:
    submission = get_submission_by_id(mongo_db, submission_id)
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    assignment = get_assignment_by_id(mongo_db, submission.assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    course = get_course_by_id(mongo_db, assignment.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    student = get_user_by_id(mongo_db, submission.student_id)
    return _to_submission_response(submission, student=student, assignment=assignment)


def grade_submission(
    mongo_db: Database,
    submission_id: int,
    grade_in: SubmissionGradePayload,
    instructor_user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> SubmissionResponse:
    submission = get_submission_by_id(mongo_db, submission_id)
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")

    assignment = get_assignment_by_id(mongo_db, submission.assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    course = get_course_by_id(mongo_db, assignment.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, instructor_user)

    if grade_in.grade < 0 or grade_in.grade > assignment.max_marks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Grade must be between 0 and {assignment.max_marks} marks.",
        )

    now = datetime.now(timezone.utc)
    updated = update_submission_doc(
        mongo_db,
        submission.id,
        {
            "grade": float(grade_in.grade),
            "feedback": grade_in.feedback.strip() if grade_in.feedback else None,
            "status": "graded",
            "graded_by_id": instructor_user.id,
            "graded_at": now,
            "updated_at": now,
        },
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    try:
        sync_submission_to_sqlite_shadow(sqlite_db, updated)
    except Exception:
        restore_submission_snapshot(mongo_db, submission)
        raise

    student = get_user_by_id(mongo_db, updated.student_id)
    return _to_submission_response(updated, student=student, assignment=assignment)


# ---------------------------------------------------------------------------
# Student Service Operations
# ---------------------------------------------------------------------------


def list_course_assignments_for_student(
    mongo_db: Database,
    course_id: int,
    current_user: MongoUser,
) -> List[AssignmentResponse]:
    check_student_course_access(mongo_db, course_id, current_user)

    assignments = list_assignments_for_course(
        mongo_db,
        course_id,
        published_only=True,
        exclude_archived=True,
        sort_asc=True,
    )
    sub_map = list_submissions_for_student_assignments(
        mongo_db,
        current_user.id,
        [a.id for a in assignments],
    )

    return [
        _build_assignment_response(
            a,
            my_submission=_to_submission_summary(sub_map[a.id]) if a.id in sub_map else None,
        )
        for a in assignments
    ]


def get_assignment_detail_for_student(
    mongo_db: Database,
    assignment_id: int,
    current_user: MongoUser,
) -> AssignmentDetailResponse:
    assignment = get_assignment_by_id(mongo_db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")

    course = check_student_course_access(mongo_db, assignment.course_id, current_user)

    if current_user.role not in ("instructor", "admin") and current_user.id != course.instructor_id:
        if not assignment.is_published or assignment.is_archived:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment is not available.",
            )

    section = (
        get_section_by_id(mongo_db, assignment.section_id)
        if assignment.section_id is not None
        else None
    )
    my_sub = get_submission_by_assignment_and_student(mongo_db, assignment_id, current_user.id)

    return AssignmentDetailResponse(
        id=assignment.id,
        course_id=assignment.course_id,
        section_id=assignment.section_id,
        title=assignment.title,
        description=assignment.description,
        instructions=assignment.instructions,
        max_marks=assignment.max_marks,
        due_date=assignment.due_date,
        is_published=assignment.is_published,
        is_closed=assignment.is_closed,
        allow_resubmission=assignment.allow_resubmission,
        is_archived=assignment.is_archived,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
        course_title=course.title,
        section_title=section.title if section else None,
        my_submission=_to_submission_summary(my_sub) if my_sub else None,
    )


def submit_student_assignment(
    mongo_db: Database,
    assignment_id: int,
    submission_in: SubmissionCreate,
    current_user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> SubmissionResponse:
    assignment = get_assignment_by_id(mongo_db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")

    check_student_course_access(mongo_db, assignment.course_id, current_user)

    if not assignment.is_published or assignment.is_archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit to an unpublished or archived assignment.",
        )

    if assignment.is_closed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This assignment has been closed for submissions by the instructor.",
        )

    now = datetime.now(timezone.utc)
    due = normalize_utc(assignment.due_date)
    is_late = bool(due and now > due)

    existing_sub = get_submission_by_assignment_and_student(
        mongo_db,
        assignment_id,
        current_user.id,
    )

    if existing_sub:
        if not assignment.allow_resubmission:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resubmissions are disabled for this assignment.",
            )
        new_status = "resubmitted" if existing_sub.status == "graded" else existing_sub.status
        updated = update_submission_doc(
            mongo_db,
            existing_sub.id,
            {
                "submission_text": submission_in.submission_text.strip(),
                "attachments_json": submission_in.attachments_json,
                "updated_at": now,
                "is_late": is_late,
                "status": new_status,
            },
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
        try:
            sync_submission_to_sqlite_shadow(sqlite_db, updated)
        except Exception:
            restore_submission_snapshot(mongo_db, existing_sub)
            raise
        return _to_submission_response(updated, student=current_user, assignment=assignment)

    new_sub = create_submission_doc(
        mongo_db,
        assignment_id=assignment_id,
        student_id=current_user.id,
        submission_text=submission_in.submission_text,
        attachments_json=submission_in.attachments_json,
        is_late=is_late,
        now=now,
    )
    try:
        sync_submission_to_sqlite_shadow(sqlite_db, new_sub)
    except Exception:
        delete_submission_doc(mongo_db, new_sub.id)
        raise

    return _to_submission_response(new_sub, student=current_user, assignment=assignment)


def get_student_submission(
    mongo_db: Database,
    assignment_id: int,
    current_user: MongoUser,
) -> Optional[SubmissionResponse]:
    assignment = get_assignment_by_id(mongo_db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")

    check_student_course_access(mongo_db, assignment.course_id, current_user)

    sub = get_submission_by_assignment_and_student(mongo_db, assignment_id, current_user.id)
    if not sub:
        return None

    return _to_submission_response(sub, student=current_user, assignment=assignment)
