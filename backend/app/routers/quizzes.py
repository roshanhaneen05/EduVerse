from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.quiz import Quiz
from app.models.user import User
from app.schemas.quiz import (
    QuizAttemptResult,
    QuizAttemptSummary,
    QuizResponse,
    QuizStartResponse,
    QuizSubmission,
)
from app.services.quiz_service import (
    evaluate_quiz_submission,
    get_attempt_detail,
    get_quiz_for_student,
    list_user_attempts,
    start_quiz_attempt,
)

router = APIRouter(prefix="/quizzes", tags=["Quizzes & Assessments"])


@router.get(
    "/course/{course_id}",
    response_model=List[QuizResponse],
    summary="List available published quizzes for a course",
)
def get_course_quizzes(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve all published quizzes for an enrolled course or instructor."""
    is_manager = current_user.role in ("instructor", "admin")
    query = db.query(Quiz).filter(Quiz.course_id == course_id)
    if not is_manager:
        query = query.filter(Quiz.is_published == True)
    quizzes = query.order_by(Quiz.id.asc()).all()

    return [get_quiz_for_student(db, q.id, current_user) for q in quizzes]


@router.get(
    "/my-history",
    response_model=List[QuizAttemptSummary],
    summary="Get current user's past quiz attempt history",
)
def get_my_attempts(
    quiz_id: Optional[int] = Query(None, description="Filter attempts by quiz ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_user_attempts(db, user_id=current_user.id, quiz_id=quiz_id)


@router.get(
    "/attempts/{attempt_id}",
    response_model=QuizAttemptResult,
    summary="Get full attempt result and post-submission review",
)
def get_attempt(
    attempt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_attempt_detail(db, attempt_id, current_user)


@router.post(
    "/{quiz_id}/start",
    response_model=QuizStartResponse,
    status_code=status.HTTP_200_OK,
    summary="Start an assessment attempt session with timer calculation",
)
def start_quiz(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return start_quiz_attempt(db, quiz_id, current_user)


@router.get(
    "/{quiz_id}",
    response_model=QuizResponse,
    summary="Get quiz questions and answer options for taking assessment",
)
def get_quiz(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_quiz_for_student(db, quiz_id, current_user)


@router.post(
    "/{quiz_id}/submit",
    response_model=QuizAttemptResult,
    summary="Submit answers for evaluation and score calculation",
)
def submit_quiz(
    quiz_id: int,
    submission: QuizSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return evaluate_quiz_submission(db, quiz_id, current_user, submission)
