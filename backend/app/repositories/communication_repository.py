import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.announcement import CourseAnnouncement
from app.models.discussion import CourseDiscussion, DiscussionReply
from app.models.email_delivery import EmailDelivery
from app.models.notification import Notification
from app.mongo_schema import next_sequence_id, sync_counter
from app.repositories.user_repository import _ensure_utc

logger = logging.getLogger(__name__)


@dataclass
class MongoCourseAnnouncement:
    id: int
    course_id: int
    instructor_id: int
    title: str
    content: str
    is_published: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoCourseAnnouncement":
        now = datetime.now(timezone.utc)
        return cls(
            id=int(doc["id"]),
            course_id=int(doc["course_id"]),
            instructor_id=int(doc["instructor_id"]),
            title=str(doc["title"]),
            content=str(doc["content"]),
            is_published=bool(doc.get("is_published", True)),
            created_at=_ensure_utc(doc.get("created_at")) or now,
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
        )


@dataclass
class MongoCourseDiscussion:
    id: int
    course_id: int
    user_id: int
    title: str
    content: str
    is_pinned: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoCourseDiscussion":
        now = datetime.now(timezone.utc)
        return cls(
            id=int(doc["id"]),
            course_id=int(doc["course_id"]),
            user_id=int(doc["user_id"]),
            title=str(doc["title"]),
            content=str(doc["content"]),
            is_pinned=bool(doc.get("is_pinned", False)),
            is_deleted=bool(doc.get("is_deleted", False)),
            created_at=_ensure_utc(doc.get("created_at")) or now,
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
        )


@dataclass
class MongoDiscussionReply:
    id: int
    thread_id: int
    user_id: int
    parent_reply_id: Optional[int]
    content: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoDiscussionReply":
        now = datetime.now(timezone.utc)
        pid = doc.get("parent_reply_id")
        return cls(
            id=int(doc["id"]),
            thread_id=int(doc["thread_id"]),
            user_id=int(doc["user_id"]),
            parent_reply_id=int(pid) if pid is not None else None,
            content=str(doc["content"]),
            is_deleted=bool(doc.get("is_deleted", False)),
            created_at=_ensure_utc(doc.get("created_at")) or now,
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
        )


@dataclass
class MongoNotification:
    id: int
    user_id: int
    title: str
    message: str
    notification_type: str
    link_url: Optional[str]
    is_read: bool
    created_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoNotification":
        now = datetime.now(timezone.utc)
        return cls(
            id=int(doc["id"]),
            user_id=int(doc["user_id"]),
            title=str(doc["title"]),
            message=str(doc["message"]),
            notification_type=str(doc["notification_type"]),
            link_url=doc.get("link_url"),
            is_read=bool(doc.get("is_read", False)),
            created_at=_ensure_utc(doc.get("created_at")) or now,
        )


@dataclass
class MongoEmailDelivery:
    id: int
    enrollment_id: int
    event_type: str
    recipient_email: str
    status: str
    attempts: int
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime]

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoEmailDelivery":
        now = datetime.now(timezone.utc)
        return cls(
            id=int(doc["id"]),
            enrollment_id=int(doc["enrollment_id"]),
            event_type=str(doc["event_type"]),
            recipient_email=str(doc["recipient_email"]),
            status=str(doc.get("status", "pending")),
            attempts=int(doc.get("attempts", 0)),
            last_error=doc.get("last_error"),
            created_at=_ensure_utc(doc.get("created_at")) or now,
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
            sent_at=_ensure_utc(doc.get("sent_at")),
        )


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------


def get_announcement_by_id(
    mongo_db: Database,
    announcement_id: int,
) -> Optional[MongoCourseAnnouncement]:
    doc = mongo_db["course_announcements"].find_one({"id": int(announcement_id)})
    return MongoCourseAnnouncement.from_doc(doc) if doc else None


def list_announcements_for_course(
    mongo_db: Database,
    course_id: int,
    *,
    published_only: bool = False,
) -> List[MongoCourseAnnouncement]:
    filt: Dict[str, Any] = {"course_id": int(course_id)}
    if published_only:
        filt["is_published"] = True
    cursor = mongo_db["course_announcements"].find(filt).sort("created_at", DESCENDING)
    return [MongoCourseAnnouncement.from_doc(d) for d in cursor]


def create_announcement_doc(
    mongo_db: Database,
    *,
    course_id: int,
    instructor_id: int,
    title: str,
    content: str,
    is_published: bool,
) -> MongoCourseAnnouncement:
    now = datetime.now(timezone.utc)
    ann_id = next_sequence_id(mongo_db, "course_announcements")
    doc = {
        "id": ann_id,
        "course_id": int(course_id),
        "instructor_id": int(instructor_id),
        "title": title.strip(),
        "content": content.strip(),
        "is_published": bool(is_published),
        "created_at": now,
        "updated_at": now,
    }
    mongo_db["course_announcements"].insert_one(doc)
    return MongoCourseAnnouncement.from_doc(doc)


def update_announcement_doc(
    mongo_db: Database,
    announcement_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoCourseAnnouncement]:
    payload = dict(updates)
    payload["updated_at"] = datetime.now(timezone.utc)
    doc = mongo_db["course_announcements"].find_one_and_update(
        {"id": int(announcement_id)},
        {"$set": payload},
        return_document=ReturnDocument.AFTER,
    )
    return MongoCourseAnnouncement.from_doc(doc) if doc else None


def restore_announcement_snapshot(
    mongo_db: Database,
    prev: MongoCourseAnnouncement,
) -> None:
    mongo_db["course_announcements"].update_one(
        {"id": prev.id},
        {
            "$set": {
                "course_id": prev.course_id,
                "instructor_id": prev.instructor_id,
                "title": prev.title,
                "content": prev.content,
                "is_published": prev.is_published,
                "created_at": prev.created_at,
                "updated_at": prev.updated_at,
            }
        },
        upsert=True,
    )


def delete_announcement_doc(mongo_db: Database, announcement_id: int) -> None:
    mongo_db["course_announcements"].delete_one({"id": int(announcement_id)})


# ---------------------------------------------------------------------------
# Discussions & Replies
# ---------------------------------------------------------------------------


def get_discussion_by_id(
    mongo_db: Database,
    discussion_id: int,
) -> Optional[MongoCourseDiscussion]:
    doc = mongo_db["course_discussions"].find_one({"id": int(discussion_id)})
    return MongoCourseDiscussion.from_doc(doc) if doc else None


def list_discussions_paginated(
    mongo_db: Database,
    course_id: int,
    *,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[int, List[MongoCourseDiscussion]]:
    filt: Dict[str, Any] = {"course_id": int(course_id)}
    if search and search.strip():
        pattern = re.escape(search.strip())
        filt["$or"] = [
            {"title": {"$regex": pattern, "$options": "i"}},
            {"content": {"$regex": pattern, "$options": "i"}},
        ]
    total = int(mongo_db["course_discussions"].count_documents(filt))
    skip = (page - 1) * page_size
    cursor = (
        mongo_db["course_discussions"]
        .find(filt)
        .sort([("is_pinned", DESCENDING), ("created_at", DESCENDING)])
        .skip(skip)
        .limit(page_size)
    )
    return total, [MongoCourseDiscussion.from_doc(d) for d in cursor]


def count_active_replies_by_thread_ids(
    mongo_db: Database,
    thread_ids: Iterable[int],
) -> Dict[int, int]:
    ids = [int(t) for t in thread_ids]
    if not ids:
        return {}
    pipeline = [
        {"$match": {"thread_id": {"$in": ids}, "is_deleted": False}},
        {"$group": {"_id": "$thread_id", "count": {"$sum": 1}}},
    ]
    return {
        int(row["_id"]): int(row["count"])
        for row in mongo_db["discussion_replies"].aggregate(pipeline)
    }


def create_discussion_doc(
    mongo_db: Database,
    *,
    course_id: int,
    user_id: int,
    title: str,
    content: str,
) -> MongoCourseDiscussion:
    now = datetime.now(timezone.utc)
    disc_id = next_sequence_id(mongo_db, "course_discussions")
    doc = {
        "id": disc_id,
        "course_id": int(course_id),
        "user_id": int(user_id),
        "title": title.strip(),
        "content": content.strip(),
        "is_pinned": False,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }
    mongo_db["course_discussions"].insert_one(doc)
    return MongoCourseDiscussion.from_doc(doc)


def update_discussion_doc(
    mongo_db: Database,
    discussion_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoCourseDiscussion]:
    payload = dict(updates)
    payload["updated_at"] = datetime.now(timezone.utc)
    doc = mongo_db["course_discussions"].find_one_and_update(
        {"id": int(discussion_id)},
        {"$set": payload},
        return_document=ReturnDocument.AFTER,
    )
    return MongoCourseDiscussion.from_doc(doc) if doc else None


def restore_discussion_snapshot(
    mongo_db: Database,
    prev: MongoCourseDiscussion,
) -> None:
    mongo_db["course_discussions"].update_one(
        {"id": prev.id},
        {
            "$set": {
                "course_id": prev.course_id,
                "user_id": prev.user_id,
                "title": prev.title,
                "content": prev.content,
                "is_pinned": prev.is_pinned,
                "is_deleted": prev.is_deleted,
                "created_at": prev.created_at,
                "updated_at": prev.updated_at,
            }
        },
        upsert=True,
    )


def delete_discussion_doc(mongo_db: Database, discussion_id: int) -> None:
    mongo_db["discussion_replies"].delete_many({"thread_id": int(discussion_id)})
    mongo_db["course_discussions"].delete_one({"id": int(discussion_id)})


def get_reply_by_id(
    mongo_db: Database,
    reply_id: int,
) -> Optional[MongoDiscussionReply]:
    doc = mongo_db["discussion_replies"].find_one({"id": int(reply_id)})
    return MongoDiscussionReply.from_doc(doc) if doc else None


def list_replies_for_thread(
    mongo_db: Database,
    thread_id: int,
) -> List[MongoDiscussionReply]:
    cursor = (
        mongo_db["discussion_replies"]
        .find({"thread_id": int(thread_id)})
        .sort("created_at", ASCENDING)
    )
    return [MongoDiscussionReply.from_doc(d) for d in cursor]


def create_reply_doc(
    mongo_db: Database,
    *,
    thread_id: int,
    user_id: int,
    parent_reply_id: Optional[int],
    content: str,
) -> MongoDiscussionReply:
    now = datetime.now(timezone.utc)
    reply_id = next_sequence_id(mongo_db, "discussion_replies")
    doc = {
        "id": reply_id,
        "thread_id": int(thread_id),
        "user_id": int(user_id),
        "parent_reply_id": int(parent_reply_id) if parent_reply_id is not None else None,
        "content": content.strip(),
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }
    mongo_db["discussion_replies"].insert_one(doc)
    return MongoDiscussionReply.from_doc(doc)


def update_reply_doc(
    mongo_db: Database,
    reply_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoDiscussionReply]:
    payload = dict(updates)
    payload["updated_at"] = datetime.now(timezone.utc)
    doc = mongo_db["discussion_replies"].find_one_and_update(
        {"id": int(reply_id)},
        {"$set": payload},
        return_document=ReturnDocument.AFTER,
    )
    return MongoDiscussionReply.from_doc(doc) if doc else None


def restore_reply_snapshot(
    mongo_db: Database,
    prev: MongoDiscussionReply,
) -> None:
    mongo_db["discussion_replies"].update_one(
        {"id": prev.id},
        {
            "$set": {
                "thread_id": prev.thread_id,
                "user_id": prev.user_id,
                "parent_reply_id": prev.parent_reply_id,
                "content": prev.content,
                "is_deleted": prev.is_deleted,
                "created_at": prev.created_at,
                "updated_at": prev.updated_at,
            }
        },
        upsert=True,
    )


def delete_reply_doc(mongo_db: Database, reply_id: int) -> None:
    mongo_db["discussion_replies"].delete_one({"id": int(reply_id)})


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


def get_notification_by_id(
    mongo_db: Database,
    notification_id: int,
) -> Optional[MongoNotification]:
    doc = mongo_db["notifications"].find_one({"id": int(notification_id)})
    return MongoNotification.from_doc(doc) if doc else None


def list_notifications_for_user(
    mongo_db: Database,
    user_id: int,
    *,
    unread_only: bool = False,
    limit: int = 50,
) -> List[MongoNotification]:
    filt: Dict[str, Any] = {"user_id": int(user_id)}
    if unread_only:
        filt["is_read"] = False
    cursor = (
        mongo_db["notifications"]
        .find(filt)
        .sort([("created_at", DESCENDING), ("id", DESCENDING)])
        .limit(limit)
    )
    return [MongoNotification.from_doc(d) for d in cursor]


def count_unread_notifications(mongo_db: Database, user_id: int) -> int:
    return int(
        mongo_db["notifications"].count_documents(
            {"user_id": int(user_id), "is_read": False}
        )
    )


def create_notification_doc(
    mongo_db: Database,
    *,
    user_id: int,
    title: str,
    message: str,
    notification_type: str,
    link_url: Optional[str] = None,
) -> MongoNotification:
    now = datetime.now(timezone.utc)
    notif_id = next_sequence_id(mongo_db, "notifications")
    doc = {
        "id": notif_id,
        "user_id": int(user_id),
        "title": title,
        "message": message,
        "notification_type": notification_type,
        "link_url": link_url,
        "is_read": False,
        "created_at": now,
    }
    mongo_db["notifications"].insert_one(doc)
    return MongoNotification.from_doc(doc)


def create_notifications_bulk_docs(
    mongo_db: Database,
    *,
    user_ids: Iterable[int],
    title: str,
    message: str,
    notification_type: str,
    link_url: Optional[str] = None,
) -> List[MongoNotification]:
    docs = []
    now = datetime.now(timezone.utc)
    for uid in user_ids:
        notif_id = next_sequence_id(mongo_db, "notifications")
        docs.append(
            {
                "id": notif_id,
                "user_id": int(uid),
                "title": title,
                "message": message,
                "notification_type": notification_type,
                "link_url": link_url,
                "is_read": False,
                "created_at": now,
            }
        )
    if docs:
        mongo_db["notifications"].insert_many(docs)
    return [MongoNotification.from_doc(d) for d in docs]


def mark_notification_read_doc(
    mongo_db: Database,
    notification_id: int,
) -> Optional[MongoNotification]:
    doc = mongo_db["notifications"].find_one_and_update(
        {"id": int(notification_id)},
        {"$set": {"is_read": True}},
        return_document=ReturnDocument.AFTER,
    )
    return MongoNotification.from_doc(doc) if doc else None


def mark_all_notifications_read_doc(mongo_db: Database, user_id: int) -> int:
    result = mongo_db["notifications"].update_many(
        {"user_id": int(user_id), "is_read": False},
        {"$set": {"is_read": True}},
    )
    return int(result.modified_count)


def delete_notification_doc(mongo_db: Database, notification_id: int) -> int:
    res = mongo_db["notifications"].delete_one({"id": int(notification_id)})
    return int(res.deleted_count)


# ---------------------------------------------------------------------------
# Email Deliveries
# ---------------------------------------------------------------------------


def get_email_delivery_by_id(
    mongo_db: Database,
    delivery_id: int,
) -> Optional[MongoEmailDelivery]:
    doc = mongo_db["email_deliveries"].find_one({"id": int(delivery_id)})
    return MongoEmailDelivery.from_doc(doc) if doc else None


def get_email_delivery_by_enrollment_event(
    mongo_db: Database,
    enrollment_id: int,
    event_type: str,
) -> Optional[MongoEmailDelivery]:
    doc = mongo_db["email_deliveries"].find_one(
        {"enrollment_id": int(enrollment_id), "event_type": event_type}
    )
    return MongoEmailDelivery.from_doc(doc) if doc else None


def list_email_deliveries_by_status(
    mongo_db: Database,
    delivery_status: str,
) -> List[MongoEmailDelivery]:
    cursor = (
        mongo_db["email_deliveries"]
        .find({"status": delivery_status})
        .sort("updated_at", ASCENDING)
    )
    return [MongoEmailDelivery.from_doc(d) for d in cursor]


def create_email_delivery_doc(
    mongo_db: Database,
    *,
    enrollment_id: int,
    event_type: str,
    recipient_email: str,
) -> MongoEmailDelivery:
    now = datetime.now(timezone.utc)
    delivery_id = next_sequence_id(mongo_db, "email_deliveries")
    doc = {
        "id": delivery_id,
        "enrollment_id": int(enrollment_id),
        "event_type": event_type,
        "recipient_email": recipient_email,
        "status": "pending",
        "attempts": 0,
        "last_error": None,
        "created_at": now,
        "updated_at": now,
        "sent_at": None,
    }
    try:
        mongo_db["email_deliveries"].insert_one(doc)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email delivery record already exists for this enrollment event.",
        ) from exc
    return MongoEmailDelivery.from_doc(doc)


def claim_email_delivery_for_sending(
    mongo_db: Database,
    delivery_id: int,
) -> Optional[MongoEmailDelivery]:
    doc = mongo_db["email_deliveries"].find_one_and_update(
        {"id": int(delivery_id), "status": {"$in": ["pending", "failed"]}},
        {
            "$set": {
                "status": "sending",
                "last_error": None,
                "updated_at": datetime.now(timezone.utc),
            },
            "$inc": {"attempts": 1},
        },
        return_document=ReturnDocument.AFTER,
    )
    return MongoEmailDelivery.from_doc(doc) if doc else None


def update_email_delivery_doc(
    mongo_db: Database,
    delivery_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoEmailDelivery]:
    payload = dict(updates)
    payload["updated_at"] = datetime.now(timezone.utc)
    doc = mongo_db["email_deliveries"].find_one_and_update(
        {"id": int(delivery_id)},
        {"$set": payload},
        return_document=ReturnDocument.AFTER,
    )
    return MongoEmailDelivery.from_doc(doc) if doc else None


def delete_email_delivery_doc(mongo_db: Database, delivery_id: int) -> None:
    mongo_db["email_deliveries"].delete_one({"id": int(delivery_id)})


# ---------------------------------------------------------------------------
# Transitional SQLite Shadow Sync Helpers
# ---------------------------------------------------------------------------


def sync_announcement_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    ann: MongoCourseAnnouncement,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = (
            sqlite_db.query(CourseAnnouncement)
            .filter(CourseAnnouncement.id == ann.id)
            .first()
        )
        if row is None:
            row = CourseAnnouncement(
                id=ann.id,
                course_id=ann.course_id,
                instructor_id=ann.instructor_id,
                title=ann.title,
                content=ann.content,
                is_published=ann.is_published,
                created_at=ann.created_at,
                updated_at=ann.updated_at,
            )
            sqlite_db.add(row)
        else:
            row.title = ann.title
            row.content = ann.content
            row.is_published = ann.is_published
            row.updated_at = ann.updated_at
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for announcement_id=%s: %s", ann.id, type(exc).__name__)
        raise


def delete_announcement_from_sqlite_shadow(
    sqlite_db: Optional[Session],
    announcement_id: int,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = (
            sqlite_db.query(CourseAnnouncement)
            .filter(CourseAnnouncement.id == announcement_id)
            .first()
        )
        if row is not None:
            sqlite_db.delete(row)
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow delete failed for announcement_id=%s: %s", announcement_id, type(exc).__name__)
        raise


def sync_discussion_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    disc: MongoCourseDiscussion,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(CourseDiscussion).filter(CourseDiscussion.id == disc.id).first()
        if row is None:
            row = CourseDiscussion(
                id=disc.id,
                course_id=disc.course_id,
                user_id=disc.user_id,
                title=disc.title,
                content=disc.content,
                is_pinned=disc.is_pinned,
                is_deleted=disc.is_deleted,
                created_at=disc.created_at,
                updated_at=disc.updated_at,
            )
            sqlite_db.add(row)
        else:
            row.title = disc.title
            row.content = disc.content
            row.is_pinned = disc.is_pinned
            row.is_deleted = disc.is_deleted
            row.updated_at = disc.updated_at
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for discussion_id=%s: %s", disc.id, type(exc).__name__)
        raise


def sync_reply_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    reply: MongoDiscussionReply,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(DiscussionReply).filter(DiscussionReply.id == reply.id).first()
        if row is None:
            row = DiscussionReply(
                id=reply.id,
                thread_id=reply.thread_id,
                user_id=reply.user_id,
                parent_reply_id=reply.parent_reply_id,
                content=reply.content,
                is_deleted=reply.is_deleted,
                created_at=reply.created_at,
                updated_at=reply.updated_at,
            )
            sqlite_db.add(row)
        else:
            row.content = reply.content
            row.is_deleted = reply.is_deleted
            row.updated_at = reply.updated_at
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for reply_id=%s: %s", reply.id, type(exc).__name__)
        raise


def sync_notification_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    notif: MongoNotification,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(Notification).filter(Notification.id == notif.id).first()
        if row is None:
            row = Notification(
                id=notif.id,
                user_id=notif.user_id,
                title=notif.title,
                message=notif.message,
                notification_type=notif.notification_type,
                link_url=notif.link_url,
                is_read=notif.is_read,
                created_at=notif.created_at,
            )
            sqlite_db.add(row)
        else:
            row.is_read = notif.is_read
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for notification_id=%s: %s", notif.id, type(exc).__name__)
        raise


def sync_notifications_bulk_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    notifs: List[MongoNotification],
) -> None:
    if sqlite_db is None or not notifs:
        return
    try:
        for n in notifs:
            sqlite_db.add(
                Notification(
                    id=n.id,
                    user_id=n.user_id,
                    title=n.title,
                    message=n.message,
                    notification_type=n.notification_type,
                    link_url=n.link_url,
                    is_read=n.is_read,
                    created_at=n.created_at,
                )
            )
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow bulk sync failed for notifications: %s", type(exc).__name__)
        raise


def mark_all_notifications_read_sqlite_shadow(
    sqlite_db: Optional[Session],
    user_id: int,
) -> None:
    if sqlite_db is None:
        return
    try:
        sqlite_db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        ).update({"is_read": True}, synchronize_session="fetch")
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow mark-all-read failed: %s", type(exc).__name__)
        raise


def delete_notification_from_sqlite_shadow(
    sqlite_db: Optional[Session],
    notification_id: int,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(Notification).filter(Notification.id == notification_id).first()
        if row is not None:
            sqlite_db.delete(row)
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow delete failed for notification_id=%s: %s", notification_id, type(exc).__name__)
        raise


def sync_email_delivery_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    delivery: MongoEmailDelivery,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(EmailDelivery).filter(EmailDelivery.id == delivery.id).first()
        if row is None:
            row = EmailDelivery(
                id=delivery.id,
                enrollment_id=delivery.enrollment_id,
                event_type=delivery.event_type,
                recipient_email=delivery.recipient_email,
                status=delivery.status,
                attempts=delivery.attempts,
                last_error=delivery.last_error,
                created_at=delivery.created_at,
                updated_at=delivery.updated_at,
                sent_at=delivery.sent_at,
            )
            sqlite_db.add(row)
        else:
            row.status = delivery.status
            row.attempts = delivery.attempts
            row.last_error = delivery.last_error
            row.updated_at = delivery.updated_at
            row.sent_at = delivery.sent_at
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for email_delivery_id=%s: %s", delivery.id, type(exc).__name__)
        raise


def delete_email_delivery_from_sqlite_shadow(
    sqlite_db: Optional[Session],
    delivery_id: int,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = sqlite_db.query(EmailDelivery).filter(EmailDelivery.id == delivery_id).first()
        if row is not None:
            sqlite_db.delete(row)
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow delete failed for email_delivery_id=%s: %s", delivery_id, type(exc).__name__)
        raise


def sync_sqlite_communications_to_mongo(
    sqlite_db: Session,
    mongo_db: Database,
) -> Dict[str, int]:
    """Seed helper: copy SQLite announcements, discussions, replies, notifications, email_deliveries."""
    counts: Dict[str, int] = {}

    anns = sqlite_db.query(CourseAnnouncement).order_by(CourseAnnouncement.id.asc()).all()
    max_id = 0
    for a in anns:
        doc = {
            "id": int(a.id),
            "course_id": int(a.course_id),
            "instructor_id": int(a.instructor_id),
            "title": a.title,
            "content": a.content,
            "is_published": bool(a.is_published),
            "created_at": _ensure_utc(a.created_at) or datetime.now(timezone.utc),
            "updated_at": _ensure_utc(a.updated_at) or datetime.now(timezone.utc),
        }
        mongo_db["course_announcements"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        max_id = max(max_id, doc["id"])
    sync_counter(mongo_db, "course_announcements", max_id)
    counts["course_announcements"] = len(anns)

    discs = sqlite_db.query(CourseDiscussion).order_by(CourseDiscussion.id.asc()).all()
    max_did = 0
    for d in discs:
        doc = {
            "id": int(d.id),
            "course_id": int(d.course_id),
            "user_id": int(d.user_id),
            "title": d.title,
            "content": d.content,
            "is_pinned": bool(d.is_pinned),
            "is_deleted": bool(d.is_deleted),
            "created_at": _ensure_utc(d.created_at) or datetime.now(timezone.utc),
            "updated_at": _ensure_utc(d.updated_at) or datetime.now(timezone.utc),
        }
        mongo_db["course_discussions"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        max_did = max(max_did, doc["id"])
    sync_counter(mongo_db, "course_discussions", max_did)
    counts["course_discussions"] = len(discs)

    replies = sqlite_db.query(DiscussionReply).order_by(DiscussionReply.id.asc()).all()
    max_rid = 0
    for r in replies:
        doc = {
            "id": int(r.id),
            "thread_id": int(r.thread_id),
            "user_id": int(r.user_id),
            "parent_reply_id": int(r.parent_reply_id) if r.parent_reply_id is not None else None,
            "content": r.content,
            "is_deleted": bool(r.is_deleted),
            "created_at": _ensure_utc(r.created_at) or datetime.now(timezone.utc),
            "updated_at": _ensure_utc(r.updated_at) or datetime.now(timezone.utc),
        }
        mongo_db["discussion_replies"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        max_rid = max(max_rid, doc["id"])
    sync_counter(mongo_db, "discussion_replies", max_rid)
    counts["discussion_replies"] = len(replies)

    notifs = sqlite_db.query(Notification).order_by(Notification.id.asc()).all()
    max_nid = 0
    for n in notifs:
        doc = {
            "id": int(n.id),
            "user_id": int(n.user_id),
            "title": n.title,
            "message": n.message,
            "notification_type": n.notification_type,
            "link_url": n.link_url,
            "is_read": bool(n.is_read),
            "created_at": _ensure_utc(n.created_at) or datetime.now(timezone.utc),
        }
        mongo_db["notifications"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        max_nid = max(max_nid, doc["id"])
    sync_counter(mongo_db, "notifications", max_nid)
    counts["notifications"] = len(notifs)

    deliveries = sqlite_db.query(EmailDelivery).order_by(EmailDelivery.id.asc()).all()
    max_eid = 0
    for e in deliveries:
        doc = {
            "id": int(e.id),
            "enrollment_id": int(e.enrollment_id),
            "event_type": e.event_type,
            "recipient_email": e.recipient_email,
            "status": e.status,
            "attempts": int(e.attempts),
            "last_error": e.last_error,
            "created_at": _ensure_utc(e.created_at) or datetime.now(timezone.utc),
            "updated_at": _ensure_utc(e.updated_at) or datetime.now(timezone.utc),
            "sent_at": _ensure_utc(e.sent_at),
        }
        mongo_db["email_deliveries"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        max_eid = max(max_eid, doc["id"])
    sync_counter(mongo_db, "email_deliveries", max_eid)
    counts["email_deliveries"] = len(deliveries)

    return counts
