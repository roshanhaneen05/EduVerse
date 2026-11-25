from fastapi import APIRouter, Depends
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, get_mongo_db
from app.repositories.user_repository import MongoUser
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
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_lesson_for_user(mongo_db, lesson_id, current_user)


@router.post(
    "/{lesson_id}/complete",
    response_model=LessonProgressResponse,
    summary="Mark lesson completed by current student",
)
def complete_lesson(
    lesson_id: int,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return mark_lesson_complete(mongo_db, lesson_id, current_user, sqlite_db=db)
