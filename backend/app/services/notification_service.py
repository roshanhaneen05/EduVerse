from typing import List, Optional
from fastapi import HTTPException, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.repositories.communication_repository import (
    MongoNotification,
    count_unread_notifications,
    create_notification_doc,
    create_notifications_bulk_docs,
    delete_notification_doc,
    delete_notification_from_sqlite_shadow,
    get_notification_by_id,
    list_notifications_for_user,
    mark_all_notifications_read_doc,
    mark_all_notifications_read_sqlite_shadow,
    mark_notification_read_doc,
    sync_notification_to_sqlite_shadow,
    sync_notifications_bulk_to_sqlite_shadow,
)
from app.repositories.course_repository import list_enrollments_for_courses


def create_notification(
    mongo_db: Database,
    user_id: int,
    title: str,
    message: str,
    notification_type: str,
    link_url: Optional[str] = None,
    sqlite_db: Optional[Session] = None,
) -> MongoNotification:
    """Create a persistent notification record in MongoDB (and shadow-sync to SQLite)."""
    notif = create_notification_doc(
        mongo_db,
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        link_url=link_url,
    )
    try:
        sync_notification_to_sqlite_shadow(sqlite_db, notif)
    except Exception:
        delete_notification_doc(mongo_db, notif.id)
        raise
    return notif


def notify_enrolled_students(
    mongo_db: Database,
    course_id: int,
    title: str,
    message: str,
    notification_type: str,
    link_url: Optional[str] = None,
    exclude_user_id: Optional[int] = None,
    sqlite_db: Optional[Session] = None,
) -> int:
    """Notify approved students in a course, excluding the sender."""
    enrollments = list_enrollments_for_courses(
        mongo_db,
        course_ids=[course_id],
        status_filter="approved",
        sort_asc=True,
    )
    target_user_ids = [
        enr.student_id
        for enr in enrollments
        if exclude_user_id is None or enr.student_id != exclude_user_id
    ]
    if not target_user_ids:
        return 0

    created = create_notifications_bulk_docs(
        mongo_db,
        user_ids=target_user_ids,
        title=title,
        message=message,
        notification_type=notification_type,
        link_url=link_url,
    )
    try:
        sync_notifications_bulk_to_sqlite_shadow(sqlite_db, created)
    except Exception:
        for n in created:
            delete_notification_doc(mongo_db, n.id)
        raise
    return len(created)


def list_user_notifications(
    mongo_db: Database,
    user_id: int,
    unread_only: bool = False,
    limit: int = 50,
) -> List[MongoNotification]:
    """Retrieve notifications strictly for the authenticated user."""
    return list_notifications_for_user(
        mongo_db,
        user_id=user_id,
        unread_only=unread_only,
        limit=limit,
    )


def get_unread_count(mongo_db: Database, user_id: int) -> int:
    """Count unread notifications for a user."""
    return count_unread_notifications(mongo_db, user_id)


def mark_notification_as_read(
    mongo_db: Database,
    notification_id: int,
    user_id: int,
    sqlite_db: Optional[Session] = None,
) -> MongoNotification:
    """Mark a single notification as read, ensuring it belongs to the user."""
    notif = get_notification_by_id(mongo_db, notification_id)
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    if notif.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this notification.",
        )

    if not notif.is_read:
        updated = mark_notification_read_doc(mongo_db, notification_id)
        if updated:
            sync_notification_to_sqlite_shadow(sqlite_db, updated)
            return updated
    return notif


def mark_all_notifications_as_read(
    mongo_db: Database,
    user_id: int,
    sqlite_db: Optional[Session] = None,
) -> int:
    """Mark all unread notifications of the user as read."""
    count = mark_all_notifications_read_doc(mongo_db, user_id)
    if count > 0:
        mark_all_notifications_read_sqlite_shadow(sqlite_db, user_id)
    return count


def delete_notification(
    mongo_db: Database,
    notification_id: int,
    user_id: int,
    sqlite_db: Optional[Session] = None,
) -> None:
    """Delete a notification belonging strictly to the authenticated user."""
    notif = get_notification_by_id(mongo_db, notification_id)
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    if notif.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this notification.",
        )
    delete_notification_doc(mongo_db, notification_id)
    delete_notification_from_sqlite_shadow(sqlite_db, notification_id)
