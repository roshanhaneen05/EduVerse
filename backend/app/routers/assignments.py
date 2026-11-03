from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.assignment import (
    AssignmentDetailResponse,
    AssignmentResponse,
    SubmissionCreate,
    SubmissionResponse,
)
from app.services.assignment_service import (
    get_assignment_detail_for_student,
    get_student_submission,
    list_course_assignments_for_student,
    submit_student_assignment,
)

router = APIRouter(prefix="/assignments", tags=["Assignments & Student Submissions"])


@router.get(
    "/course/{course_id}",
    response_model=List[AssignmentResponse],
    summary="List published assignments for a course (student/enrolled view)",
)
def get_course_assignments(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_course_assignments_for_student(db, course_id, current_user)


@router.get(
    "/{assignment_id}",
    response_model=AssignmentDetailResponse,
    summary="Get assignment details and personal submission status",
)
def get_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_assignment_detail_for_student(db, assignment_id, current_user)


@router.post(
    "/{assignment_id}/submit",
    response_model=SubmissionResponse,
    summary="Submit or resubmit written work for an assignment",
)
def submit_assignment(
    assignment_id: int,
    submission_in: SubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return submit_student_assignment(db, assignment_id, submission_in, current_user)


@router.get(
    "/{assignment_id}/my-submission",
    response_model=Optional[SubmissionResponse],
    summary="Get current user's submission and grading feedback for an assignment",
)
def get_my_submission(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_student_submission(db, assignment_id, current_user)

