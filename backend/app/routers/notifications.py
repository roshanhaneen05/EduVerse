from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.notification import (
    MarkAllReadResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.services.notification_service import (
    get_unread_count as service_get_unread_count,
    list_user_notifications as service_list_user_notifications,
    mark_all_notifications_as_read as service_mark_all_notifications_as_read,
    mark_notification_as_read as service_mark_notification_as_read,
)

router = APIRouter(prefix="/notifications", tags=["User Notifications"])


@router.get(
    "",
    response_model=List[NotificationResponse],
    summary="List persistent notifications for the current authenticated user",
)
def get_user_notifications(
    unread_only: bool = Query(False, description="Filter only unread notifications"),
    limit: int = Query(50, ge=1, le=100, description="Max notifications to retrieve"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service_list_user_notifications(
        db=db,
        user_id=current_user.id,
        unread_only=unread_only,
        limit=limit,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Get count of unread notifications for current user",
)
def get_unread_count_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = service_get_unread_count(db=db, user_id=current_user.id)
    return UnreadCountResponse(unread_count=count)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark a specific notification as read",
)
def mark_as_read_endpoint(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service_mark_notification_as_read(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
    )


@router.post(
    "/mark-all-read",
    response_model=MarkAllReadResponse,
    summary="Mark all unread notifications as read for current user",
)
def mark_all_read_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = service_mark_all_notifications_as_read(
        db=db,
        user_id=current_user.id,
    )
    return MarkAllReadResponse(
        message="All notifications marked as read.",
        updated_count=updated,
    )

