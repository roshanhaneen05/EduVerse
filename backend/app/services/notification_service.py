from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.enrollment import CourseEnrollment
from app.models.notification import Notification


def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: str,
    link_url: Optional[str] = None,
) -> Notification:
    """Create a persistent notification record for a specific user."""
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        link_url=link_url,
        is_read=False,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def notify_enrolled_students(
    db: Session,
    course_id: int,
    title: str,
    message: str,
    notification_type: str,
    link_url: Optional[str] = None,
    exclude_user_id: Optional[int] = None,
) -> int:
    """Notify approved students in a course, excluding the sender."""
    enrollments = (
        db.query(CourseEnrollment)
        .filter(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.status == "approved",
        )
        .all()
    )

    notifications_to_add = []
    for enr in enrollments:
        if exclude_user_id is not None and enr.student_id == exclude_user_id:
            continue
        notifications_to_add.append(
            Notification(
                user_id=enr.student_id,
                title=title,
                message=message,
                notification_type=notification_type,
                link_url=link_url,
                is_read=False,
            )
        )

    if notifications_to_add:
        db.add_all(notifications_to_add)
        db.commit()

    return len(notifications_to_add)


def list_user_notifications(
    db: Session,
    user_id: int,
    unread_only: bool = False,
    limit: int = 50,
) -> List[Notification]:
    """Retrieve notifications strictly for the authenticated user."""
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    return query.order_by(Notification.created_at.desc()).limit(limit).all()


def get_unread_count(db: Session, user_id: int) -> int:
    """Count unread notifications for a user."""
    count = (
        db.query(func.count(Notification.id))
        .filter(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .scalar()
    )
    return count or 0


def mark_notification_as_read(
    db: Session,
    notification_id: int,
    user_id: int,
) -> Notification:
    """Mark a single notification as read, ensuring it belongs to the user."""
    notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id)
        .first()
    )
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
        notif.is_read = True
        db.commit()
        db.refresh(notif)
    return notif


def mark_all_notifications_as_read(
    db: Session,
    user_id: int,
) -> int:
    """Mark all unread notifications of the user as read."""
    unread_notifs = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .all()
    )
    count = len(unread_notifs)
    for notif in unread_notifs:
        notif.is_read = True

    if count > 0:
        db.commit()
    return count
