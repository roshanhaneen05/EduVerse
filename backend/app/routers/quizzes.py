from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, get_mongo_db
from app.repositories.quiz_repository import list_quizzes_for_course
from app.repositories.user_repository import MongoUser
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
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    """Retrieve all published quizzes for an enrolled course or instructor."""
    is_manager = current_user.role in ("instructor", "admin")
    quizzes = list_quizzes_for_course(
        mongo_db,
        course_id,
        published_only=not is_manager,
    )
    return [get_quiz_for_student(mongo_db, q.id, current_user) for q in quizzes]


@router.get(
    "/my-history",
    response_model=List[QuizAttemptSummary],
    summary="Get current user's past quiz attempt history",
)
def get_my_attempts(
    quiz_id: Optional[int] = Query(None, description="Filter attempts by quiz ID"),
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    return list_user_attempts(mongo_db, user_id=current_user.id, quiz_id=quiz_id)


@router.get(
    "/attempts/{attempt_id}",
    response_model=QuizAttemptResult,
    summary="Get full attempt result and post-submission review",
)
def get_attempt(
    attempt_id: int,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_attempt_detail(mongo_db, attempt_id, current_user)


@router.post(
    "/{quiz_id}/start",
    response_model=QuizStartResponse,
    status_code=status.HTTP_200_OK,
    summary="Start an assessment attempt session with timer calculation",
)
def start_quiz(
    quiz_id: int,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return start_quiz_attempt(mongo_db, quiz_id, current_user, sqlite_db=db)


@router.get(
    "/{quiz_id}",
    response_model=QuizResponse,
    summary="Get quiz questions and answer options for taking assessment",
)
def get_quiz(
    quiz_id: int,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_quiz_for_student(mongo_db, quiz_id, current_user)


@router.post(
    "/{quiz_id}/submit",
    response_model=QuizAttemptResult,
    summary="Submit answers for evaluation and score calculation",
)
def submit_quiz(
    quiz_id: int,
    submission: QuizSubmission,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return evaluate_quiz_submission(mongo_db, quiz_id, current_user, submission, sqlite_db=db)
