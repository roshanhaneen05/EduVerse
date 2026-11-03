from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.lesson import LessonProgressResponse, LessonResponse
from app.services.lesson_service import get_lesson_for_user, mark_lesson_complete

router = APIRouter(prefix="/lessons", tags=["Lessons & Learning"])


@router.get(
    "/{lesson_id}",
    response_model=LessonResponse,
    summary="Get lesson content by ID",
)
def get_lesson(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_lesson_for_user(db, lesson_id, current_user)


@router.post(
    "/{lesson_id}/complete",
    response_model=LessonProgressResponse,
    summary="Mark lesson completed by current student",
)
def complete_lesson(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return mark_lesson_complete(db, lesson_id, current_user)

