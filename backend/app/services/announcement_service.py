from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.announcement import CourseAnnouncement
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.user import User
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate
from app.services.notification_service import notify_enrolled_students


def check_course_instructor_or_admin(course: Course, user: User):
    """Verify that user is the course instructor owner or an administrator."""
    if user.role != "admin" and course.instructor_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage announcements for this course.",
        )


def check_course_access(db: Session, course_id: int, user: User) -> Course:
    """Verify course exists and user is enrolled, the course instructor, or an admin."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    # Instructors who own the course or admins have full access
    if user.role == "admin" or course.instructor_id == user.id:
        return course

    # Students must be actively enrolled
    enrollment = (
        db.query(CourseEnrollment)
        .filter(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.student_id == user.id,
            CourseEnrollment.status == "approved",
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be enrolled in this course to view announcements.",
        )

    return course


def list_course_announcements(
    db: Session,
    course_id: int,
    user: User,
) -> List[CourseAnnouncement]:
    """List announcements for a course, filtering by publication state for students."""
    course = check_course_access(db, course_id, user)

    query = (
        db.query(CourseAnnouncement)
        .options(joinedload(CourseAnnouncement.author))
        .filter(CourseAnnouncement.course_id == course_id)
    )

    is_manager = (user.role == "admin" or course.instructor_id == user.id)
    if not is_manager:
        # Students must only see published announcements
        query = query.filter(CourseAnnouncement.is_published.is_(True))

    return query.order_by(CourseAnnouncement.created_at.desc()).all()


def get_announcement_detail(
    db: Session,
    announcement_id: int,
    user: User,
) -> CourseAnnouncement:
    """Get single announcement detail with permission check."""
    announcement = (
        db.query(CourseAnnouncement)
        .options(joinedload(CourseAnnouncement.author))
        .filter(CourseAnnouncement.id == announcement_id)
        .first()
    )
    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found.",
        )

    course = check_course_access(db, announcement.course_id, user)
    is_manager = (user.role == "admin" or course.instructor_id == user.id)
    if not is_manager and not announcement.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found or not published.",
        )

    return announcement


def create_announcement(
    db: Session,
    course_id: int,
    announcement_in: AnnouncementCreate,
    user: User,
) -> CourseAnnouncement:
    """Create a new course announcement. Notifies enrolled students if published."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    check_course_instructor_or_admin(course, user)

    announcement = CourseAnnouncement(
        course_id=course_id,
        instructor_id=user.id,
        title=announcement_in.title.strip(),
        content=announcement_in.content.strip(),
        is_published=announcement_in.is_published,
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)

    # If published, generate notifications for enrolled students
    if announcement.is_published:
        notify_enrolled_students(
            db=db,
            course_id=course_id,
            title=f"New Announcement: {announcement.title}",
            message=f"{user.full_name} posted an announcement in '{course.title}': {announcement.title}",
            notification_type="announcement",
            link_url=f"/courses/{course_id}#announcements",
            exclude_user_id=user.id,
        )

    return announcement


def update_announcement(
    db: Session,
    announcement_id: int,
    announcement_in: AnnouncementUpdate,
    user: User,
) -> CourseAnnouncement:
    """Update an announcement. If transitioning to published, dispatches notifications."""
    announcement = (
        db.query(CourseAnnouncement)
        .filter(CourseAnnouncement.id == announcement_id)
        .first()
    )
    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found.",
        )

    course = db.query(Course).filter(Course.id == announcement.course_id).first()
    check_course_instructor_or_admin(course, user)

    was_published = announcement.is_published

    if announcement_in.title is not None:
        announcement.title = announcement_in.title.strip()
    if announcement_in.content is not None:
        announcement.content = announcement_in.content.strip()
    if announcement_in.is_published is not None:
        announcement.is_published = announcement_in.is_published

    db.commit()
    db.refresh(announcement)

    # If transitioning from draft to published, notify enrolled students
    if not was_published and announcement.is_published:
        notify_enrolled_students(
            db=db,
            course_id=announcement.course_id,
            title=f"New Announcement: {announcement.title}",
            message=f"{user.full_name} posted an announcement in '{course.title}': {announcement.title}",
            notification_type="announcement",
            link_url=f"/courses/{announcement.course_id}#announcements",
            exclude_user_id=user.id,
        )

    return announcement


def delete_announcement(
    db: Session,
    announcement_id: int,
    user: User,
) -> None:
    """Delete an announcement (instructor owner or admin only)."""
    announcement = (
        db.query(CourseAnnouncement)
        .filter(CourseAnnouncement.id == announcement_id)
        .first()
    )
    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found.",
        )

    course = db.query(Course).filter(Course.id == announcement.course_id).first()
    check_course_instructor_or_admin(course, user)

    db.delete(announcement)
    db.commit()
