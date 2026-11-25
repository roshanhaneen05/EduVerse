from typing import List
from fastapi import APIRouter, Depends, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, get_mongo_db, require_instructor
from app.repositories.user_repository import MongoUser
from app.schemas.announcement import (
    AnnouncementCreate,
    AnnouncementResponse,
    AnnouncementUpdate,
)
from app.schemas.common import MessageResponse
from app.services.announcement_service import (
    create_announcement as service_create_announcement,
    delete_announcement as service_delete_announcement,
    get_announcement_detail as service_get_announcement_detail,
    list_course_announcements as service_list_course_announcements,
    update_announcement as service_update_announcement,
)

router = APIRouter(tags=["Course Announcements"])


@router.get(
    "/courses/{course_id}/announcements",
    response_model=List[AnnouncementResponse],
    summary="List announcements for a course (enrolled students view published; instructors/admins view all)",
)
def list_announcements(
    course_id: int,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    return service_list_course_announcements(mongo_db, course_id, current_user)


@router.post(
    "/courses/{course_id}/announcements",
    response_model=AnnouncementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new course announcement (instructor owner or admin only)",
)
def create_announcement_endpoint(
    course_id: int,
    announcement_in: AnnouncementCreate,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return service_create_announcement(
        mongo_db,
        course_id,
        announcement_in,
        current_user,
        sqlite_db=db,
    )


@router.get(
    "/announcements/{announcement_id}",
    response_model=AnnouncementResponse,
    summary="Get announcement details",
)
def get_announcement_endpoint(
    announcement_id: int,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    return service_get_announcement_detail(mongo_db, announcement_id, current_user)


@router.put(
    "/announcements/{announcement_id}",
    response_model=AnnouncementResponse,
    summary="Update course announcement (instructor owner or admin only)",
)
def update_announcement_endpoint(
    announcement_id: int,
    announcement_in: AnnouncementUpdate,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return service_update_announcement(
        mongo_db,
        announcement_id,
        announcement_in,
        current_user,
        sqlite_db=db,
    )


@router.delete(
    "/announcements/{announcement_id}",
    response_model=MessageResponse,
    summary="Delete course announcement (instructor owner or admin only)",
)
def delete_announcement_endpoint(
    announcement_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    service_delete_announcement(mongo_db, announcement_id, current_user, sqlite_db=db)
    return MessageResponse(message="Announcement deleted successfully.")
