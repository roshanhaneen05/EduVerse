from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.assignment import Assignment, AssignmentSubmission
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.section import CourseSection
from app.models.user import User
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


def check_course_ownership(course: Course, user: User):
    """Ensure the user is the course instructor or an administrator."""
    if user.role != "admin" and course.instructor_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage assignments for this course.",
        )


def check_student_course_access(db: Session, course_id: int, user: User) -> Course:
    """Verify course exists and user is either enrolled, the course instructor, or an admin."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    if user.role != "admin" and course.instructor_id != user.id:
        enrollment = (
            db.query(CourseEnrollment)
            .filter(
                CourseEnrollment.student_id == user.id,
                CourseEnrollment.course_id == course_id,
            )
            .first()
        )
        if not enrollment:
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


# ---------------------------------------------------------------------------
# Instructor Service Operations
# ---------------------------------------------------------------------------


def create_assignment(
    db: Session,
    course_id: int,
    assignment_in: AssignmentCreate,
    current_user: User,
) -> AssignmentResponse:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    if assignment_in.section_id:
        sec = (
            db.query(CourseSection)
            .filter(CourseSection.id == assignment_in.section_id, CourseSection.course_id == course_id)
            .first()
        )
        if not sec:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target section does not exist in this course.",
            )

    assignment = Assignment(
        course_id=course_id,
        section_id=assignment_in.section_id,
        title=assignment_in.title.strip(),
        description=assignment_in.description.strip() if assignment_in.description else None,
        instructions=assignment_in.instructions.strip(),
        max_marks=assignment_in.max_marks,
        due_date=assignment_in.due_date,
        is_published=assignment_in.is_published,
        is_closed=False,
        allow_resubmission=assignment_in.allow_resubmission,
        is_archived=False,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

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
        submission_count=0,
        graded_count=0,
    )


def update_assignment(
    db: Session,
    assignment_id: int,
    assignment_in: AssignmentUpdate,
    current_user: User,
) -> AssignmentResponse:
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    course = db.query(Course).filter(Course.id == assignment.course_id).first()
    check_course_ownership(course, current_user)

    if assignment_in.title is not None:
        assignment.title = assignment_in.title.strip()
    if assignment_in.description is not None:
        assignment.description = assignment_in.description.strip() if assignment_in.description else None
    if assignment_in.instructions is not None:
        assignment.instructions = assignment_in.instructions.strip()
    if assignment_in.max_marks is not None:
        assignment.max_marks = assignment_in.max_marks
    if assignment_in.due_date is not None:
        assignment.due_date = assignment_in.due_date
    if assignment_in.section_id is not None:
        sec = (
            db.query(CourseSection)
            .filter(CourseSection.id == assignment_in.section_id, CourseSection.course_id == assignment.course_id)
            .first()
        )
        if not sec:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target section does not exist in this course.",
            )
        assignment.section_id = assignment_in.section_id
    if assignment_in.allow_resubmission is not None:
        assignment.allow_resubmission = assignment_in.allow_resubmission
    if assignment_in.is_published is not None:
        assignment.is_published = assignment_in.is_published
    if assignment_in.is_closed is not None:
        assignment.is_closed = assignment_in.is_closed
    if assignment_in.is_archived is not None:
        assignment.is_archived = assignment_in.is_archived

    db.commit()
    db.refresh(assignment)

    sub_count = db.query(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == assignment.id).count()
    graded_count = (
        db.query(AssignmentSubmission)
        .filter(AssignmentSubmission.assignment_id == assignment.id, AssignmentSubmission.grade.isnot(None))
        .count()
    )

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
        submission_count=sub_count,
        graded_count=graded_count,
    )


def toggle_assignment_status(
    db: Session,
    assignment_id: int,
    attribute: str,
    current_user: User,
) -> AssignmentResponse:
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    course = db.query(Course).filter(Course.id == assignment.course_id).first()
    check_course_ownership(course, current_user)

    current_val = getattr(assignment, attribute)
    setattr(assignment, attribute, not current_val)
    db.commit()
    db.refresh(assignment)

    sub_count = db.query(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == assignment.id).count()
    graded_count = (
        db.query(AssignmentSubmission)
        .filter(AssignmentSubmission.assignment_id == assignment.id, AssignmentSubmission.grade.isnot(None))
        .count()
    )

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
        submission_count=sub_count,
        graded_count=graded_count,
    )


def delete_assignment(
    db: Session,
    assignment_id: int,
    current_user: User,
    archive_if_submissions: bool = False,
) -> dict:
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    course = db.query(Course).filter(Course.id == assignment.course_id).first()
    check_course_ownership(course, current_user)

    sub_count = db.query(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == assignment.id).count()
    if sub_count > 0:
        if archive_if_submissions:
            assignment.is_archived = True
            assignment.is_published = False
            db.commit()
            return {"message": "Assignment contains student submissions and has been safely archived.", "archived": True}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot permanently delete an assignment that contains student submissions. Archive it instead to preserve grading history.",
            )

    db.delete(assignment)
    db.commit()
    return {"message": "Assignment successfully deleted.", "archived": False}


def list_instructor_assignments(db: Session, course_id: int, current_user: User) -> List[AssignmentResponse]:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    assignments = (
        db.query(Assignment)
        .filter(Assignment.course_id == course_id)
        .order_by(Assignment.created_at.desc())
        .all()
    )

    results = []
    for a in assignments:
        sub_count = db.query(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == a.id).count()
        graded_count = (
            db.query(AssignmentSubmission)
            .filter(AssignmentSubmission.assignment_id == a.id, AssignmentSubmission.grade.isnot(None))
            .count()
        )
        results.append(
            AssignmentResponse(
                id=a.id,
                course_id=a.course_id,
                section_id=a.section_id,
                title=a.title,
                description=a.description,
                instructions=a.instructions,
                max_marks=a.max_marks,
                due_date=a.due_date,
                is_published=a.is_published,
                is_closed=a.is_closed,
                allow_resubmission=a.allow_resubmission,
                is_archived=a.is_archived,
                created_at=a.created_at,
                updated_at=a.updated_at,
                submission_count=sub_count,
                graded_count=graded_count,
            )
        )
    return results


def get_assignment_submissions_for_instructor(
    db: Session,
    assignment_id: int,
    current_user: User,
) -> List[SubmissionResponse]:
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    course = db.query(Course).filter(Course.id == assignment.course_id).first()
    check_course_ownership(course, current_user)

    submissions = (
        db.query(AssignmentSubmission)
        .options(joinedload(AssignmentSubmission.student))
        .filter(AssignmentSubmission.assignment_id == assignment_id)
        .order_by(AssignmentSubmission.submitted_at.desc())
        .all()
    )

    return [
        SubmissionResponse(
            id=s.id,
            assignment_id=s.assignment_id,
            student_id=s.student_id,
            student=StudentSummary(id=s.student.id, full_name=s.student.full_name, email=s.student.email)
            if s.student
            else None,
            submission_text=s.submission_text,
            attachments_json=s.attachments_json,
            status=s.status,
            is_late=s.is_late,
            submitted_at=s.submitted_at,
            updated_at=s.updated_at,
            grade=s.grade,
            feedback=s.feedback,
            graded_by_id=s.graded_by_id,
            graded_at=s.graded_at,
            assignment_title=assignment.title,
            max_marks=assignment.max_marks,
        )
        for s in submissions
    ]


def grade_submission(
    db: Session,
    submission_id: int,
    grade_in: SubmissionGradePayload,
    instructor_user: User,
) -> SubmissionResponse:
    submission = (
        db.query(AssignmentSubmission)
        .options(joinedload(AssignmentSubmission.assignment), joinedload(AssignmentSubmission.student))
        .filter(AssignmentSubmission.id == submission_id)
        .first()
    )
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")

    assignment = submission.assignment
    course = db.query(Course).filter(Course.id == assignment.course_id).first()
    check_course_ownership(course, instructor_user)

    if grade_in.grade < 0 or grade_in.grade > assignment.max_marks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Grade must be between 0 and {assignment.max_marks} marks.",
        )

    submission.grade = grade_in.grade
    submission.feedback = grade_in.feedback.strip() if grade_in.feedback else None
    submission.status = "graded"
    submission.graded_by_id = instructor_user.id
    submission.graded_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(submission)

    return SubmissionResponse(
        id=submission.id,
        assignment_id=submission.assignment_id,
        student_id=submission.student_id,
        student=StudentSummary(
            id=submission.student.id,
            full_name=submission.student.full_name,
            email=submission.student.email,
        )
        if submission.student
        else None,
        submission_text=submission.submission_text,
        attachments_json=submission.attachments_json,
        status=submission.status,
        is_late=submission.is_late,
        submitted_at=submission.submitted_at,
        updated_at=submission.updated_at,
        grade=submission.grade,
        feedback=submission.feedback,
        graded_by_id=submission.graded_by_id,
        graded_at=submission.graded_at,
        assignment_title=assignment.title,
        max_marks=assignment.max_marks,
    )


# ---------------------------------------------------------------------------
# Student Service Operations
# ---------------------------------------------------------------------------


def list_course_assignments_for_student(
    db: Session,
    course_id: int,
    current_user: User,
) -> List[AssignmentResponse]:
    check_student_course_access(db, course_id, current_user)

    assignments = (
        db.query(Assignment)
        .filter(
            Assignment.course_id == course_id,
            Assignment.is_published == True,
            Assignment.is_archived == False,
        )
        .order_by(Assignment.created_at.asc())
        .all()
    )

    assignment_ids = [a.id for a in assignments]
    submissions = (
        db.query(AssignmentSubmission)
        .filter(
            AssignmentSubmission.student_id == current_user.id,
            AssignmentSubmission.assignment_id.in_(assignment_ids),
        )
        .all()
    )
    sub_map = {s.assignment_id: s for s in submissions}

    results = []
    for a in assignments:
        my_sub = sub_map.get(a.id)
        sub_summary = (
            SubmissionSummary(
                id=my_sub.id,
                student_id=my_sub.student_id,
                status=my_sub.status,
                submitted_at=my_sub.submitted_at,
                is_late=my_sub.is_late,
                grade=my_sub.grade,
                feedback=my_sub.feedback,
                graded_at=my_sub.graded_at,
            )
            if my_sub
            else None
        )

        results.append(
            AssignmentResponse(
                id=a.id,
                course_id=a.course_id,
                section_id=a.section_id,
                title=a.title,
                description=a.description,
                instructions=a.instructions,
                max_marks=a.max_marks,
                due_date=a.due_date,
                is_published=a.is_published,
                is_closed=a.is_closed,
                allow_resubmission=a.allow_resubmission,
                is_archived=a.is_archived,
                created_at=a.created_at,
                updated_at=a.updated_at,
                my_submission=sub_summary,
            )
        )
    return results


def get_assignment_detail_for_student(
    db: Session,
    assignment_id: int,
    current_user: User,
) -> AssignmentDetailResponse:
    assignment = (
        db.query(Assignment)
        .options(joinedload(Assignment.course), joinedload(Assignment.section))
        .filter(Assignment.id == assignment_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")

    check_student_course_access(db, assignment.course_id, current_user)

    if (
        current_user.role not in ("instructor", "admin")
        and current_user.id != assignment.course.instructor_id
    ):
        if not assignment.is_published or assignment.is_archived:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment is not available.",
            )

    my_sub = (
        db.query(AssignmentSubmission)
        .filter(
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.student_id == current_user.id,
        )
        .first()
    )

    sub_summary = (
        SubmissionSummary(
            id=my_sub.id,
            student_id=my_sub.student_id,
            status=my_sub.status,
            submitted_at=my_sub.submitted_at,
            is_late=my_sub.is_late,
            grade=my_sub.grade,
            feedback=my_sub.feedback,
            graded_at=my_sub.graded_at,
        )
        if my_sub
        else None
    )

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
        course_title=assignment.course.title if assignment.course else None,
        section_title=assignment.section.title if assignment.section else None,
        my_submission=sub_summary,
    )


def submit_student_assignment(
    db: Session,
    assignment_id: int,
    submission_in: SubmissionCreate,
    current_user: User,
) -> SubmissionResponse:
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")

    check_student_course_access(db, assignment.course_id, current_user)

    if not assignment.is_published or assignment.is_archived:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot submit to an unpublished or archived assignment.")

    if assignment.is_closed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This assignment has been closed for submissions by the instructor.",
        )

    now = datetime.now(timezone.utc)
    due = normalize_utc(assignment.due_date)
    is_late = bool(due and now > due)

    existing_sub = (
        db.query(AssignmentSubmission)
        .filter(
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.student_id == current_user.id,
        )
        .first()
    )

    if existing_sub:
        if not assignment.allow_resubmission:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resubmissions are disabled for this assignment.",
            )
        existing_sub.submission_text = submission_in.submission_text.strip()
        existing_sub.attachments_json = submission_in.attachments_json
        existing_sub.updated_at = now
        existing_sub.is_late = is_late
        if existing_sub.status == "graded":
            existing_sub.status = "resubmitted"

        db.commit()
        db.refresh(existing_sub)
        return SubmissionResponse(
            id=existing_sub.id,
            assignment_id=existing_sub.assignment_id,
            student_id=existing_sub.student_id,
            student=StudentSummary(id=current_user.id, full_name=current_user.full_name, email=current_user.email),
            submission_text=existing_sub.submission_text,
            attachments_json=existing_sub.attachments_json,
            status=existing_sub.status,
            is_late=existing_sub.is_late,
            submitted_at=existing_sub.submitted_at,
            updated_at=existing_sub.updated_at,
            grade=existing_sub.grade,
            feedback=existing_sub.feedback,
            graded_by_id=existing_sub.graded_by_id,
            graded_at=existing_sub.graded_at,
            assignment_title=assignment.title,
            max_marks=assignment.max_marks,
        )

    new_sub = AssignmentSubmission(
        assignment_id=assignment_id,
        student_id=current_user.id,
        submission_text=submission_in.submission_text.strip(),
        attachments_json=submission_in.attachments_json,
        status="submitted",
        is_late=is_late,
        submitted_at=now,
        updated_at=now,
    )
    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)

    return SubmissionResponse(
        id=new_sub.id,
        assignment_id=new_sub.assignment_id,
        student_id=new_sub.student_id,
        student=StudentSummary(id=current_user.id, full_name=current_user.full_name, email=current_user.email),
        submission_text=new_sub.submission_text,
        attachments_json=new_sub.attachments_json,
        status=new_sub.status,
        is_late=new_sub.is_late,
        submitted_at=new_sub.submitted_at,
        updated_at=new_sub.updated_at,
        grade=None,
        feedback=None,
        graded_by_id=None,
        graded_at=None,
        assignment_title=assignment.title,
        max_marks=assignment.max_marks,
    )


def get_student_submission(
    db: Session,
    assignment_id: int,
    current_user: User,
) -> Optional[SubmissionResponse]:
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")

    check_student_course_access(db, assignment.course_id, current_user)

    sub = (
        db.query(AssignmentSubmission)
        .filter(
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.student_id == current_user.id,
        )
        .first()
    )
    if not sub:
        return None

    return SubmissionResponse(
        id=sub.id,
        assignment_id=sub.assignment_id,
        student_id=sub.student_id,
        student=StudentSummary(id=current_user.id, full_name=current_user.full_name, email=current_user.email),
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
