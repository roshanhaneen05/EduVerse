import math
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.course import Course
from app.models.discussion import CourseDiscussion, DiscussionReply
from app.models.enrollment import CourseEnrollment
from app.models.user import User
from app.schemas.discussion import (
    DiscussionCreate,
    DiscussionDetailResponse,
    DiscussionListItem,
    DiscussionUpdate,
    PaginatedDiscussionsResponse,
    ReplyCreate,
    ReplyResponse,
    ReplyUpdate,
)
from app.services.notification_service import create_notification


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
            detail="You must be enrolled in this course to access discussions.",
        )

    return course


def can_moderate_or_author(course: Course, author_id: int, user: User) -> bool:
    """Check if the user is the original author, course instructor, or platform admin."""
    return user.id == author_id or course.instructor_id == user.id or user.role == "admin"


def list_course_discussions(
    db: Session,
    course_id: int,
    user: User,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedDiscussionsResponse:
    """List paginated discussion threads for a course, with search and reply counts."""
    course = check_course_access(db, course_id, user)

    query = (
        db.query(CourseDiscussion)
        .options(joinedload(CourseDiscussion.author))
        .filter(CourseDiscussion.course_id == course_id)
    )

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (CourseDiscussion.title.ilike(term)) | (CourseDiscussion.content.ilike(term))
        )

    total = query.count()
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1

    # Order by is_pinned descending, then created_at descending
    threads = (
        query.order_by(CourseDiscussion.is_pinned.desc(), CourseDiscussion.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Batch query reply counts for the threads on this page
    thread_ids = [t.id for t in threads]
    reply_counts = {}
    if thread_ids:
        counts = (
            db.query(DiscussionReply.thread_id, func.count(DiscussionReply.id))
            .filter(
                DiscussionReply.thread_id.in_(thread_ids),
                DiscussionReply.is_deleted.is_(False),
            )
            .group_by(DiscussionReply.thread_id)
            .all()
        )
        reply_counts = dict(counts)

    items: List[DiscussionListItem] = []
    for t in threads:
        display_title = "[Removed Thread]" if t.is_deleted else t.title
        display_content = "[This discussion thread has been removed by the author or a moderator.]" if t.is_deleted else t.content
        items.append(
            DiscussionListItem(
                id=t.id,
                course_id=t.course_id,
                user_id=t.user_id,
                title=display_title,
                content=display_content,
                is_pinned=t.is_pinned,
                is_deleted=t.is_deleted,
                reply_count=reply_counts.get(t.id, 0),
                created_at=t.created_at,
                updated_at=t.updated_at,
                author=t.author,
            )
        )

    return PaginatedDiscussionsResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
    )


def get_discussion_detail(
    db: Session,
    discussion_id: int,
    user: User,
) -> DiscussionDetailResponse:
    """Retrieve full thread details with chronological replies."""
    thread = (
        db.query(CourseDiscussion)
        .options(joinedload(CourseDiscussion.author))
        .filter(CourseDiscussion.id == discussion_id)
        .first()
    )
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion thread not found.",
        )

    course = check_course_access(db, thread.course_id, user)

    # Fetch all replies in chronological order
    replies = (
        db.query(DiscussionReply)
        .options(joinedload(DiscussionReply.author))
        .filter(DiscussionReply.thread_id == discussion_id)
        .order_by(DiscussionReply.created_at.asc())
        .all()
    )

    reply_items: List[ReplyResponse] = []
    for r in replies:
        content = "[This reply has been deleted by the author or a moderator.]" if r.is_deleted else r.content
        reply_items.append(
            ReplyResponse(
                id=r.id,
                thread_id=r.thread_id,
                user_id=r.user_id,
                parent_reply_id=r.parent_reply_id,
                content=content,
                is_deleted=r.is_deleted,
                created_at=r.created_at,
                updated_at=r.updated_at,
                author=r.author,
            )
        )

    display_title = "[Removed Thread]" if thread.is_deleted else thread.title
    display_content = "[This discussion thread has been removed by the author or a moderator.]" if thread.is_deleted else thread.content

    return DiscussionDetailResponse(
        id=thread.id,
        course_id=thread.course_id,
        user_id=thread.user_id,
        title=display_title,
        content=display_content,
        is_pinned=thread.is_pinned,
        is_deleted=thread.is_deleted,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        author=thread.author,
        replies=reply_items,
    )


def create_discussion(
    db: Session,
    course_id: int,
    discussion_in: DiscussionCreate,
    user: User,
) -> CourseDiscussion:
    """Create a new discussion thread in an enrolled course."""
    check_course_access(db, course_id, user)

    thread = CourseDiscussion(
        course_id=course_id,
        user_id=user.id,
        title=discussion_in.title.strip(),
        content=discussion_in.content.strip(),
        is_pinned=False,
        is_deleted=False,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def update_discussion(
    db: Session,
    discussion_id: int,
    discussion_in: DiscussionUpdate,
    user: User,
) -> CourseDiscussion:
    """Edit discussion thread. Only original author or platform admin can edit."""
    thread = (
        db.query(CourseDiscussion)
        .filter(CourseDiscussion.id == discussion_id)
        .first()
    )
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion thread not found.",
        )

    if thread.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot edit a deleted discussion thread.",
        )

    if thread.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own discussion threads.",
        )

    if discussion_in.title is not None:
        thread.title = discussion_in.title.strip()
    if discussion_in.content is not None:
        thread.content = discussion_in.content.strip()

    db.commit()
    db.refresh(thread)
    return thread


def delete_discussion(
    db: Session,
    discussion_id: int,
    user: User,
) -> None:
    """Soft-delete discussion thread. Author, course instructor, or admin can delete."""
    thread = (
        db.query(CourseDiscussion)
        .filter(CourseDiscussion.id == discussion_id)
        .first()
    )
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion thread not found.",
        )

    course = db.query(Course).filter(Course.id == thread.course_id).first()
    if not can_moderate_or_author(course, thread.user_id, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete or moderate this discussion thread.",
        )

    thread.is_deleted = True
    db.commit()


def toggle_pin_discussion(
    db: Session,
    discussion_id: int,
    user: User,
) -> CourseDiscussion:
    """Toggle pinned status for a discussion thread (course instructor or admin only)."""
    thread = (
        db.query(CourseDiscussion)
        .filter(CourseDiscussion.id == discussion_id)
        .first()
    )
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion thread not found.",
        )

    course = db.query(Course).filter(Course.id == thread.course_id).first()
    if user.role != "admin" and course.instructor_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the course instructor or an administrator can pin discussions.",
        )

    thread.is_pinned = not thread.is_pinned
    db.commit()
    db.refresh(thread)
    return thread


def create_reply(
    db: Session,
    discussion_id: int,
    reply_in: ReplyCreate,
    user: User,
) -> DiscussionReply:
    """Add a reply to a discussion thread and notify thread/parent author."""
    thread = (
        db.query(CourseDiscussion)
        .filter(CourseDiscussion.id == discussion_id)
        .first()
    )
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion thread not found.",
        )

    if thread.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reply to a deleted discussion thread.",
        )

    course = check_course_access(db, thread.course_id, user)

    parent_reply = None
    if reply_in.parent_reply_id is not None:
        parent_reply = (
            db.query(DiscussionReply)
            .filter(
                DiscussionReply.id == reply_in.parent_reply_id,
                DiscussionReply.thread_id == discussion_id,
            )
            .first()
        )
        if not parent_reply:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent reply not found in this thread.",
            )

    reply = DiscussionReply(
        thread_id=discussion_id,
        user_id=user.id,
        parent_reply_id=reply_in.parent_reply_id,
        content=reply_in.content.strip(),
        is_deleted=False,
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)

    # Dispatches notifications:
    # 1. Notify thread author if someone else replies
    if thread.user_id != user.id:
        create_notification(
            db=db,
            user_id=thread.user_id,
            title=f"New reply on '{thread.title}'",
            message=f"{user.full_name} replied to your discussion: \"{thread.title}\"",
            notification_type="discussion_reply",
            link_url=f"/courses/{thread.course_id}/discussions/{thread.id}",
        )

    # 2. If nested reply, notify parent reply author if different from thread author and replier
    if parent_reply and parent_reply.user_id != user.id and parent_reply.user_id != thread.user_id:
        create_notification(
            db=db,
            user_id=parent_reply.user_id,
            title=f"Reply to your comment on '{thread.title}'",
            message=f"{user.full_name} replied to your comment on: \"{thread.title}\"",
            notification_type="discussion_reply",
            link_url=f"/courses/{thread.course_id}/discussions/{thread.id}",
        )

    return reply


def update_reply(
    db: Session,
    reply_id: int,
    reply_in: ReplyUpdate,
    user: User,
) -> DiscussionReply:
    """Edit reply content. Author only (or admin)."""
    reply = (
        db.query(DiscussionReply)
        .filter(DiscussionReply.id == reply_id)
        .first()
    )
    if not reply:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reply not found.",
        )

    if reply.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot edit a deleted reply.",
        )

    if reply.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own replies.",
        )

    reply.content = reply_in.content.strip()
    db.commit()
    db.refresh(reply)
    return reply


def delete_reply(
    db: Session,
    reply_id: int,
    user: User,
) -> None:
    """Soft-delete reply. Author, course instructor, or admin can delete/moderate."""
    reply = (
        db.query(DiscussionReply)
        .filter(DiscussionReply.id == reply_id)
        .first()
    )
    if not reply:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reply not found.",
        )

    thread = db.query(CourseDiscussion).filter(CourseDiscussion.id == reply.thread_id).first()
    course = db.query(Course).filter(Course.id == thread.course_id).first()

    if not can_moderate_or_author(course, reply.user_id, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete or moderate this reply.",
        )

    reply.is_deleted = True
    db.commit()
