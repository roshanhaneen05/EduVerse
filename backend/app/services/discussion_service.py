import math
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.repositories.communication_repository import (
    MongoCourseDiscussion,
    MongoDiscussionReply,
    count_active_replies_by_thread_ids,
    create_discussion_doc,
    create_reply_doc,
    delete_discussion_doc,
    delete_reply_doc,
    get_discussion_by_id,
    get_reply_by_id,
    list_discussions_paginated,
    list_replies_for_thread,
    restore_discussion_snapshot,
    restore_reply_snapshot,
    sync_discussion_to_sqlite_shadow,
    sync_reply_to_sqlite_shadow,
    update_discussion_doc,
    update_reply_doc,
)
from app.repositories.course_repository import (
    MongoCourse,
    get_course_by_id,
    get_enrollment_by_student_and_course,
)
from app.repositories.user_repository import MongoUser, get_user_by_id, get_users_by_ids
from app.schemas.discussion import (
    DiscussionAuthor,
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
            detail="You must be enrolled in this course to access discussions.",
        )

    return course


def can_moderate_or_author(course: MongoCourse, author_id: int, user: MongoUser) -> bool:
    """Check if the user is the original author, course instructor, or platform admin."""
    return user.id == author_id or course.instructor_id == user.id or user.role == "admin"


def _to_author(author: Optional[MongoUser]) -> Optional[DiscussionAuthor]:
    if not author:
        return None
    return DiscussionAuthor(
        id=author.id,
        full_name=author.full_name,
        email=author.email,
        role=author.role,
    )


def _to_reply_response(
    reply: MongoDiscussionReply,
    author: Optional[MongoUser],
) -> ReplyResponse:
    content = (
        "[This reply has been deleted by the author or a moderator.]"
        if reply.is_deleted
        else reply.content
    )
    return ReplyResponse(
        id=reply.id,
        thread_id=reply.thread_id,
        user_id=reply.user_id,
        parent_reply_id=reply.parent_reply_id,
        content=content,
        is_deleted=reply.is_deleted,
        created_at=reply.created_at,
        updated_at=reply.updated_at,
        author=_to_author(author),
    )


def list_course_discussions(
    mongo_db: Database,
    course_id: int,
    user: MongoUser,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedDiscussionsResponse:
    """List paginated discussion threads for a course, with search and reply counts."""
    check_course_access(mongo_db, course_id, user)

    total, threads = list_discussions_paginated(
        mongo_db,
        course_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1

    thread_ids = [t.id for t in threads]
    reply_counts = count_active_replies_by_thread_ids(mongo_db, thread_ids)
    author_map: Dict[int, MongoUser] = get_users_by_ids(
        mongo_db,
        [t.user_id for t in threads],
    )

    items: List[DiscussionListItem] = []
    for t in threads:
        display_title = "[Removed Thread]" if t.is_deleted else t.title
        display_content = (
            "[This discussion thread has been removed by the author or a moderator.]"
            if t.is_deleted
            else t.content
        )
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
                author=_to_author(author_map.get(t.user_id)),
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
    mongo_db: Database,
    discussion_id: int,
    user: MongoUser,
) -> DiscussionDetailResponse:
    """Retrieve full thread details with chronological replies."""
    thread = get_discussion_by_id(mongo_db, discussion_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion thread not found.",
        )

    check_course_access(mongo_db, thread.course_id, user)

    replies = list_replies_for_thread(mongo_db, discussion_id)
    author_ids = [thread.user_id] + [r.user_id for r in replies]
    author_map = get_users_by_ids(mongo_db, author_ids)

    reply_items = [
        _to_reply_response(r, author_map.get(r.user_id))
        for r in replies
    ]

    display_title = "[Removed Thread]" if thread.is_deleted else thread.title
    display_content = (
        "[This discussion thread has been removed by the author or a moderator.]"
        if thread.is_deleted
        else thread.content
    )

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
        author=_to_author(author_map.get(thread.user_id)),
        replies=reply_items,
    )


def create_discussion(
    mongo_db: Database,
    course_id: int,
    discussion_in: DiscussionCreate,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> MongoCourseDiscussion:
    """Create a new discussion thread in an enrolled course."""
    check_course_access(mongo_db, course_id, user)

    thread = create_discussion_doc(
        mongo_db,
        course_id=course_id,
        user_id=user.id,
        title=discussion_in.title,
        content=discussion_in.content,
    )
    try:
        sync_discussion_to_sqlite_shadow(sqlite_db, thread)
    except Exception:
        delete_discussion_doc(mongo_db, thread.id)
        raise
    return thread


def update_discussion(
    mongo_db: Database,
    discussion_id: int,
    discussion_in: DiscussionUpdate,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> MongoCourseDiscussion:
    """Edit discussion thread. Only original author or platform admin can edit."""
    thread = get_discussion_by_id(mongo_db, discussion_id)
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

    updates: dict = {}
    if discussion_in.title is not None:
        updates["title"] = discussion_in.title.strip()
    if discussion_in.content is not None:
        updates["content"] = discussion_in.content.strip()

    updated = update_discussion_doc(mongo_db, thread.id, updates) if updates else thread
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discussion thread not found.")
    try:
        sync_discussion_to_sqlite_shadow(sqlite_db, updated)
    except Exception:
        restore_discussion_snapshot(mongo_db, thread)
        raise
    return updated


def delete_discussion(
    mongo_db: Database,
    discussion_id: int,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> None:
    """Soft-delete discussion thread. Author, course instructor, or admin can delete."""
    thread = get_discussion_by_id(mongo_db, discussion_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion thread not found.",
        )

    course = get_course_by_id(mongo_db, thread.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    if not can_moderate_or_author(course, thread.user_id, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete or moderate this discussion thread.",
        )

    updated = update_discussion_doc(mongo_db, thread.id, {"is_deleted": True})
    if updated:
        try:
            sync_discussion_to_sqlite_shadow(sqlite_db, updated)
        except Exception:
            restore_discussion_snapshot(mongo_db, thread)
            raise


def toggle_pin_discussion(
    mongo_db: Database,
    discussion_id: int,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> MongoCourseDiscussion:
    """Toggle pinned status for a discussion thread (course instructor or admin only)."""
    thread = get_discussion_by_id(mongo_db, discussion_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion thread not found.",
        )

    course = get_course_by_id(mongo_db, thread.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    if user.role != "admin" and course.instructor_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the course instructor or an administrator can pin discussions.",
        )

    updated = update_discussion_doc(mongo_db, thread.id, {"is_pinned": not thread.is_pinned})
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discussion thread not found.")
    try:
        sync_discussion_to_sqlite_shadow(sqlite_db, updated)
    except Exception:
        restore_discussion_snapshot(mongo_db, thread)
        raise
    return updated


def create_reply(
    mongo_db: Database,
    discussion_id: int,
    reply_in: ReplyCreate,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> ReplyResponse:
    """Add a reply to a discussion thread and notify thread/parent author."""
    thread = get_discussion_by_id(mongo_db, discussion_id)
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

    check_course_access(mongo_db, thread.course_id, user)

    parent_reply = None
    if reply_in.parent_reply_id is not None:
        parent_reply = get_reply_by_id(mongo_db, reply_in.parent_reply_id)
        if not parent_reply or parent_reply.thread_id != discussion_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent reply not found in this thread.",
            )

    reply = create_reply_doc(
        mongo_db,
        thread_id=discussion_id,
        user_id=user.id,
        parent_reply_id=reply_in.parent_reply_id,
        content=reply_in.content,
    )
    try:
        sync_reply_to_sqlite_shadow(sqlite_db, reply)
    except Exception:
        delete_reply_doc(mongo_db, reply.id)
        raise

    if thread.user_id != user.id:
        create_notification(
            mongo_db=mongo_db,
            user_id=thread.user_id,
            title=f"New reply on '{thread.title}'",
            message=f"{user.full_name} replied to your discussion: \"{thread.title}\"",
            notification_type="discussion_reply",
            link_url=f"/courses/{thread.course_id}/discussions/{thread.id}",
            sqlite_db=sqlite_db,
        )

    if parent_reply and parent_reply.user_id != user.id and parent_reply.user_id != thread.user_id:
        create_notification(
            mongo_db=mongo_db,
            user_id=parent_reply.user_id,
            title=f"Reply to your comment on '{thread.title}'",
            message=f"{user.full_name} replied to your comment on: \"{thread.title}\"",
            notification_type="discussion_reply",
            link_url=f"/courses/{thread.course_id}/discussions/{thread.id}",
            sqlite_db=sqlite_db,
        )

    return _to_reply_response(reply, user)


def update_reply(
    mongo_db: Database,
    reply_id: int,
    reply_in: ReplyUpdate,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> ReplyResponse:
    """Edit reply content. Author only (or admin)."""
    reply = get_reply_by_id(mongo_db, reply_id)
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

    updated = update_reply_doc(mongo_db, reply.id, {"content": reply_in.content.strip()})
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply not found.")
    try:
        sync_reply_to_sqlite_shadow(sqlite_db, updated)
    except Exception:
        restore_reply_snapshot(mongo_db, reply)
        raise

    author = get_user_by_id(mongo_db, updated.user_id)
    return _to_reply_response(updated, author)


def delete_reply(
    mongo_db: Database,
    reply_id: int,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> None:
    """Soft-delete reply. Author, course instructor, or admin can delete/moderate."""
    reply = get_reply_by_id(mongo_db, reply_id)
    if not reply:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reply not found.",
        )

    thread = get_discussion_by_id(mongo_db, reply.thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discussion thread not found.")
    course = get_course_by_id(mongo_db, thread.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    if not can_moderate_or_author(course, reply.user_id, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete or moderate this reply.",
        )

    updated = update_reply_doc(mongo_db, reply.id, {"is_deleted": True})
    if updated:
        try:
            sync_reply_to_sqlite_shadow(sqlite_db, updated)
        except Exception:
            restore_reply_snapshot(mongo_db, reply)
            raise
