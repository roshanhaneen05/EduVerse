from typing import Dict, List, Optional
from fastapi import HTTPException, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.repositories.communication_repository import (
    MongoCourseAnnouncement,
    create_announcement_doc,
    delete_announcement_doc,
    delete_announcement_from_sqlite_shadow,
    get_announcement_by_id,
    list_announcements_for_course,
    restore_announcement_snapshot,
    sync_announcement_to_sqlite_shadow,
    update_announcement_doc,
)
from app.repositories.course_repository import (
    MongoCourse,
    get_course_by_id,
    get_enrollment_by_student_and_course,
)
from app.repositories.user_repository import MongoUser, get_user_by_id, get_users_by_ids
from app.schemas.announcement import (
    AnnouncementAuthor,
    AnnouncementCreate,
    AnnouncementResponse,
    AnnouncementUpdate,
)
from app.services.notification_service import notify_enrolled_students


def check_course_instructor_or_admin(course: MongoCourse, user: MongoUser) -> None:
    """Verify that user is the course instructor owner or an administrator."""
    if user.role != "admin" and course.instructor_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage announcements for this course.",
        )


def check_course_access(mongo_db: Database, course_id: int, user: MongoUser) -> MongoCourse:
    """Verify course exists and user is enrolled, the course instructor, or an admin."""
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    if user.role == "admin" or course.instructor_id == user.id:
        return course

    enrollment = get_enrollment_by_student_and_course(mongo_db, user.id, course_id)
    if not enrollment or enrollment.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be enrolled in this course to view announcements.",
        )

    return course


def _to_announcement_response(
    ann: MongoCourseAnnouncement,
    author: Optional[MongoUser],
) -> AnnouncementResponse:
    return AnnouncementResponse(
        id=ann.id,
        course_id=ann.course_id,
        instructor_id=ann.instructor_id,
        title=ann.title,
        content=ann.content,
        is_published=ann.is_published,
        created_at=ann.created_at,
        updated_at=ann.updated_at,
        author=(
            AnnouncementAuthor(
                id=author.id,
                full_name=author.full_name,
                email=author.email,
                role=author.role,
            )
            if author
            else None
        ),
    )


def list_course_announcements(
    mongo_db: Database,
    course_id: int,
    user: MongoUser,
) -> List[AnnouncementResponse]:
    """List announcements for a course, filtering by publication state for students."""
    course = check_course_access(mongo_db, course_id, user)
    is_manager = user.role == "admin" or course.instructor_id == user.id
    anns = list_announcements_for_course(
        mongo_db,
        course_id,
        published_only=not is_manager,
    )
    author_map: Dict[int, MongoUser] = get_users_by_ids(
        mongo_db,
        [a.instructor_id for a in anns],
    )
    return [_to_announcement_response(a, author_map.get(a.instructor_id)) for a in anns]


def get_announcement_detail(
    mongo_db: Database,
    announcement_id: int,
    user: MongoUser,
) -> AnnouncementResponse:
    """Get single announcement detail with permission check."""
    announcement = get_announcement_by_id(mongo_db, announcement_id)
    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found.",
        )

    course = check_course_access(mongo_db, announcement.course_id, user)
    is_manager = user.role == "admin" or course.instructor_id == user.id
    if not is_manager and not announcement.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found or not published.",
        )

    author = get_user_by_id(mongo_db, announcement.instructor_id)
    return _to_announcement_response(announcement, author)


def create_announcement(
    mongo_db: Database,
    course_id: int,
    announcement_in: AnnouncementCreate,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> AnnouncementResponse:
    """Create a new course announcement. Notifies enrolled students if published."""
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    check_course_instructor_or_admin(course, user)

    announcement = create_announcement_doc(
        mongo_db,
        course_id=course_id,
        instructor_id=user.id,
        title=announcement_in.title,
        content=announcement_in.content,
        is_published=announcement_in.is_published,
    )
    try:
        sync_announcement_to_sqlite_shadow(sqlite_db, announcement)
    except Exception:
        delete_announcement_doc(mongo_db, announcement.id)
        raise

    if announcement.is_published:
        notify_enrolled_students(
            mongo_db=mongo_db,
            course_id=course_id,
            title=f"New Announcement: {announcement.title}",
            message=f"{user.full_name} posted an announcement in '{course.title}': {announcement.title}",
            notification_type="announcement",
            link_url=f"/courses/{course_id}#announcements",
            exclude_user_id=user.id,
            sqlite_db=sqlite_db,
        )

    return _to_announcement_response(announcement, user)


def update_announcement(
    mongo_db: Database,
    announcement_id: int,
    announcement_in: AnnouncementUpdate,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> AnnouncementResponse:
    """Update an announcement. If transitioning to published, dispatches notifications."""
    announcement = get_announcement_by_id(mongo_db, announcement_id)
    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found.",
        )

    course = get_course_by_id(mongo_db, announcement.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_instructor_or_admin(course, user)

    was_published = announcement.is_published
    updates: dict = {}
    if announcement_in.title is not None:
        updates["title"] = announcement_in.title.strip()
    if announcement_in.content is not None:
        updates["content"] = announcement_in.content.strip()
    if announcement_in.is_published is not None:
        updates["is_published"] = announcement_in.is_published

    updated = update_announcement_doc(mongo_db, announcement.id, updates) if updates else announcement
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found.")
    try:
        sync_announcement_to_sqlite_shadow(sqlite_db, updated)
    except Exception:
        restore_announcement_snapshot(mongo_db, announcement)
        raise

    if not was_published and updated.is_published:
        notify_enrolled_students(
            mongo_db=mongo_db,
            course_id=updated.course_id,
            title=f"New Announcement: {updated.title}",
            message=f"{user.full_name} posted an announcement in '{course.title}': {updated.title}",
            notification_type="announcement",
            link_url=f"/courses/{updated.course_id}#announcements",
            exclude_user_id=user.id,
            sqlite_db=sqlite_db,
        )

    author = get_user_by_id(mongo_db, updated.instructor_id)
    return _to_announcement_response(updated, author)


def delete_announcement(
    mongo_db: Database,
    announcement_id: int,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> None:
    """Delete an announcement (instructor owner or admin only)."""
    announcement = get_announcement_by_id(mongo_db, announcement_id)
    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found.",
        )

    course = get_course_by_id(mongo_db, announcement.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_instructor_or_admin(course, user)

    delete_announcement_doc(mongo_db, announcement_id)
    delete_announcement_from_sqlite_shadow(sqlite_db, announcement_id)
