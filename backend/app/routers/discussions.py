from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.discussion import (
    DiscussionCreate,
    DiscussionDetailResponse,
    DiscussionUpdate,
    PaginatedDiscussionsResponse,
    ReplyCreate,
    ReplyResponse,
    ReplyUpdate,
)
from app.services.discussion_service import (
    create_discussion as service_create_discussion,
    create_reply as service_create_reply,
    delete_discussion as service_delete_discussion,
    delete_reply as service_delete_reply,
    get_discussion_detail as service_get_discussion_detail,
    list_course_discussions as service_list_course_discussions,
    toggle_pin_discussion as service_toggle_pin_discussion,
    update_discussion as service_update_discussion,
    update_reply as service_update_reply,
)

router = APIRouter(tags=["Course Discussions"])


@router.get(
    "/courses/{course_id}/discussions",
    response_model=PaginatedDiscussionsResponse,
    summary="List course discussions with pagination and search",
)
def list_discussions(
    course_id: int,
    search: Optional[str] = Query(None, description="Search threads by title or content"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service_list_course_discussions(
        db=db,
        course_id=course_id,
        user=current_user,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/courses/{course_id}/discussions",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new discussion thread in an enrolled course",
)
def create_discussion_endpoint(
    course_id: int,
    discussion_in: DiscussionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    thread = service_create_discussion(db, course_id, discussion_in, current_user)
    return service_get_discussion_detail(db, thread.id, current_user)


@router.get(
    "/discussions/{discussion_id}",
    response_model=DiscussionDetailResponse,
    summary="Get discussion thread detail and all replies",
)
def get_discussion_endpoint(
    discussion_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service_get_discussion_detail(db, discussion_id, current_user)


@router.put(
    "/discussions/{discussion_id}",
    response_model=DiscussionDetailResponse,
    summary="Edit discussion thread (author or admin only)",
)
def update_discussion_endpoint(
    discussion_id: int,
    discussion_in: DiscussionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service_update_discussion(db, discussion_id, discussion_in, current_user)
    return service_get_discussion_detail(db, discussion_id, current_user)


@router.delete(
    "/discussions/{discussion_id}",
    response_model=MessageResponse,
    summary="Soft-delete discussion thread (author, instructor owner, or admin)",
)
def delete_discussion_endpoint(
    discussion_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service_delete_discussion(db, discussion_id, current_user)
    return MessageResponse(message="Discussion thread deleted successfully.")


@router.patch(
    "/discussions/{discussion_id}/pin",
    response_model=DiscussionDetailResponse,
    summary="Toggle pinned status of a discussion thread (instructor owner or admin only)",
)
def toggle_pin_endpoint(
    discussion_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service_toggle_pin_discussion(db, discussion_id, current_user)
    return service_get_discussion_detail(db, discussion_id, current_user)


@router.post(
    "/discussions/{discussion_id}/replies",
    response_model=ReplyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a reply to a discussion thread",
)
def create_reply_endpoint(
    discussion_id: int,
    reply_in: ReplyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reply = service_create_reply(db, discussion_id, reply_in, current_user)
    return reply


@router.put(
    "/replies/{reply_id}",
    response_model=ReplyResponse,
    summary="Edit a reply (author or admin only)",
)
def update_reply_endpoint(
    reply_id: int,
    reply_in: ReplyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service_update_reply(db, reply_id, reply_in, current_user)


@router.delete(
    "/replies/{reply_id}",
    response_model=MessageResponse,
    summary="Soft-delete a reply (author, instructor owner, or admin)",
)
def delete_reply_endpoint(
    reply_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service_delete_reply(db, reply_id, current_user)
    return MessageResponse(message="Reply deleted successfully.")

