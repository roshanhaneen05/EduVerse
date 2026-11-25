import logging
import math
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from pymongo import DESCENDING, ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.instructor import InstructorProfile
from app.models.user import User, UserRole
from app.mongo_schema import next_sequence_id, sync_counter

logger = logging.getLogger(__name__)


def _ensure_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


@dataclass
class MongoUser:
    """SQLAlchemy-free User representation backed by MongoDB `users` documents."""

    id: int
    email: str
    full_name: str
    password_hash: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @property
    def hashed_password(self) -> str:
        return self.password_hash

    @hashed_password.setter
    def hashed_password(self, value: str) -> None:
        self.password_hash = value

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoUser":
        now = datetime.now(timezone.utc)
        return cls(
            id=int(doc["id"]),
            email=str(doc["email"]),
            full_name=str(doc["full_name"]),
            password_hash=str(doc["password_hash"]),
            role=str(doc.get("role", UserRole.STUDENT.value)),
            is_active=bool(doc.get("is_active", True)),
            created_at=_ensure_utc(doc.get("created_at")) or now,
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
        )


@dataclass
class MongoInstructorProfile:
    """MongoDB representation of `instructor_profiles` documents."""

    id: int
    user_id: int
    instructor_id: str
    phone_number: str
    qualification: str
    department: str
    subject_expertise: str
    experience_years: int
    profile_photo_url: Optional[str]
    registered_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoInstructorProfile":
        return cls(
            id=int(doc["id"]),
            user_id=int(doc["user_id"]),
            instructor_id=str(doc["instructor_id"]),
            phone_number=str(doc.get("phone_number", "")),
            qualification=str(doc.get("qualification", "")),
            department=str(doc.get("department", "")),
            subject_expertise=str(doc.get("subject_expertise", "")),
            experience_years=int(doc.get("experience_years", 0)),
            profile_photo_url=doc.get("profile_photo_url"),
            registered_at=_ensure_utc(doc.get("registered_at")) or datetime.now(timezone.utc),
        )


@dataclass
class MongoInstructorPasswordToken:
    """MongoDB representation of `instructor_password_tokens` documents."""

    id: int
    user_id: int
    token_hash: str
    purpose: str
    expires_at: datetime
    used_at: Optional[datetime]
    created_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoInstructorPasswordToken":
        return cls(
            id=int(doc["id"]),
            user_id=int(doc["user_id"]),
            token_hash=str(doc["token_hash"]),
            purpose=str(doc["purpose"]),
            expires_at=_ensure_utc(doc["expires_at"]) or datetime.now(timezone.utc),
            used_at=_ensure_utc(doc.get("used_at")),
            created_at=_ensure_utc(doc.get("created_at")) or datetime.now(timezone.utc),
        )


def get_user_by_id(mongo_db: Database, user_id: int) -> Optional[MongoUser]:
    doc = mongo_db["users"].find_one({"id": int(user_id)})
    return MongoUser.from_doc(doc) if doc else None


def get_users_by_ids(mongo_db: Database, user_ids: List[int]) -> Dict[int, MongoUser]:
    ids = list({int(uid) for uid in user_ids if uid is not None})
    if not ids:
        return {}
    return {
        int(doc["id"]): MongoUser.from_doc(doc)
        for doc in mongo_db["users"].find({"id": {"$in": ids}})
    }


def get_user_by_email(mongo_db: Database, email: str) -> Optional[MongoUser]:
    normalized = normalize_email(email)
    doc = mongo_db["users"].find_one({"email": normalized})
    if not doc:
        doc = mongo_db["users"].find_one(
            {"email": {"$regex": f"^{re.escape(normalized)}$", "$options": "i"}}
        )
    return MongoUser.from_doc(doc) if doc else None


def email_exists_for_other_user(
    mongo_db: Database,
    email: str,
    exclude_user_id: Optional[int] = None,
) -> bool:
    normalized = normalize_email(email)
    filt: Dict[str, Any] = {
        "email": {"$regex": f"^{re.escape(normalized)}$", "$options": "i"}
    }
    if exclude_user_id is not None:
        filt["id"] = {"$ne": int(exclude_user_id)}
    return mongo_db["users"].find_one(filt, {"_id": 1, "id": 1}) is not None


def create_user(
    mongo_db: Database,
    *,
    email: str,
    full_name: str,
    password_hash: str,
    role: str = UserRole.STUDENT.value,
    is_active: bool = True,
) -> MongoUser:
    valid_roles = {r.value for r in UserRole}
    if role not in valid_roles:
        raise ValueError(f"Invalid user role: {role}")

    now = datetime.now(timezone.utc)
    user_id = next_sequence_id(mongo_db, "users")
    doc = {
        "id": user_id,
        "email": normalize_email(email),
        "full_name": full_name.strip(),
        "password_hash": password_hash,
        "role": role,
        "is_active": bool(is_active),
        "created_at": now,
        "updated_at": now,
    }
    try:
        mongo_db["users"].insert_one(doc)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        ) from exc
    return MongoUser.from_doc(doc)


def update_user_fields(
    mongo_db: Database,
    user_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoUser]:
    payload = dict(updates)
    if "email" in payload and payload["email"] is not None:
        payload["email"] = normalize_email(str(payload["email"]))
    payload["updated_at"] = datetime.now(timezone.utc)
    try:
        updated = mongo_db["users"].find_one_and_update(
            {"id": int(user_id)},
            {"$set": payload},
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The email address is already in use.",
        ) from exc
    return MongoUser.from_doc(updated) if updated else None


def delete_user_by_id(mongo_db: Database, user_id: int) -> None:
    mongo_db["instructor_password_tokens"].delete_many({"user_id": int(user_id)})
    mongo_db["instructor_profiles"].delete_many({"user_id": int(user_id)})
    mongo_db["users"].delete_one({"id": int(user_id)})


def list_users_paginated(
    mongo_db: Database,
    *,
    search: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[int, int, List[MongoUser]]:
    filt: Dict[str, Any] = {}
    if role:
        filt["role"] = role
    if is_active is not None:
        filt["is_active"] = bool(is_active)
    if search:
        pattern = re.escape(search.strip())
        filt["$or"] = [
            {"email": {"$regex": pattern, "$options": "i"}},
            {"full_name": {"$regex": pattern, "$options": "i"}},
        ]

    total = int(mongo_db["users"].count_documents(filt))
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    cursor = (
        mongo_db["users"]
        .find(filt)
        .sort("created_at", DESCENDING)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    users = [MongoUser.from_doc(doc) for doc in cursor]
    return total, total_pages, users


def list_all_users(
    mongo_db: Database,
    *,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> List[MongoUser]:
    filt: Dict[str, Any] = {}
    if role:
        filt["role"] = role
    if is_active is not None:
        filt["is_active"] = bool(is_active)
    cursor = mongo_db["users"].find(filt).sort("created_at", DESCENDING)
    return [MongoUser.from_doc(doc) for doc in cursor]


def count_users(
    mongo_db: Database,
    *,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> int:
    filt: Dict[str, Any] = {}
    if role:
        filt["role"] = role
    if is_active is not None:
        filt["is_active"] = bool(is_active)
    return int(mongo_db["users"].count_documents(filt))


def list_recent_users(
    mongo_db: Database,
    *,
    limit: int = 5,
    role: Optional[str] = None,
) -> List[MongoUser]:
    filt: Dict[str, Any] = {}
    if role:
        filt["role"] = role
    cursor = mongo_db["users"].find(filt).sort("created_at", DESCENDING).limit(int(limit))
    return [MongoUser.from_doc(doc) for doc in cursor]


def get_instructor_profile_by_user_id(
    mongo_db: Database,
    user_id: int,
) -> Optional[MongoInstructorProfile]:
    doc = mongo_db["instructor_profiles"].find_one({"user_id": int(user_id)})
    return MongoInstructorProfile.from_doc(doc) if doc else None


def allocate_instructor_code(mongo_db: Database) -> str:
    for _ in range(5):
        candidate = f"EV-I-{secrets.token_hex(4).upper()}"
        if not mongo_db["instructor_profiles"].find_one(
            {"instructor_id": candidate},
            {"_id": 1},
        ):
            return candidate
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Unable to allocate an instructor ID. Please try again.",
    )


def create_instructor_profile(
    mongo_db: Database,
    *,
    user_id: int,
    instructor_id: str,
    phone_number: str = "",
    qualification: str = "",
    department: str = "",
    subject_expertise: str = "",
    experience_years: int = 0,
    profile_photo_url: Optional[str] = None,
    registered_at: Optional[datetime] = None,
) -> MongoInstructorProfile:
    profile_pk = next_sequence_id(mongo_db, "instructor_profiles")
    doc = {
        "id": profile_pk,
        "user_id": int(user_id),
        "instructor_id": instructor_id,
        "phone_number": phone_number,
        "qualification": qualification,
        "department": department,
        "subject_expertise": subject_expertise,
        "experience_years": int(experience_years),
        "profile_photo_url": profile_photo_url,
        "registered_at": _ensure_utc(registered_at) or datetime.now(timezone.utc),
    }
    try:
        mongo_db["instructor_profiles"].insert_one(doc)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The email address or generated instructor ID is already in use. Please try again.",
        ) from exc
    return MongoInstructorProfile.from_doc(doc)


def ensure_instructor_profile_for_user(
    mongo_db: Database,
    user: MongoUser,
) -> MongoInstructorProfile:
    existing = get_instructor_profile_by_user_id(mongo_db, user.id)
    if existing:
        return existing
    return create_instructor_profile(
        mongo_db,
        user_id=user.id,
        instructor_id=f"EV-I-{user.id:08d}",
        registered_at=user.created_at,
    )


def update_instructor_profile_fields(
    mongo_db: Database,
    user_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoInstructorProfile]:
    if not updates:
        return get_instructor_profile_by_user_id(mongo_db, user_id)
    doc = mongo_db["instructor_profiles"].find_one_and_update(
        {"user_id": int(user_id)},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )
    return MongoInstructorProfile.from_doc(doc) if doc else None


def list_instructors_filtered(
    mongo_db: Database,
    *,
    search: Optional[str] = None,
    department: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> List[Tuple[MongoUser, MongoInstructorProfile]]:
    user_filt: Dict[str, Any] = {"role": UserRole.INSTRUCTOR.value}
    if is_active is not None:
        user_filt["is_active"] = bool(is_active)

    users = [MongoUser.from_doc(d) for d in mongo_db["users"].find(user_filt)]
    if not users:
        return []

    user_ids = [u.id for u in users]
    profile_filt: Dict[str, Any] = {"user_id": {"$in": user_ids}}
    if department:
        profile_filt["department"] = {
            "$regex": re.escape(department.strip()),
            "$options": "i",
        }
    profiles_by_uid = {
        int(p["user_id"]): MongoInstructorProfile.from_doc(p)
        for p in mongo_db["instructor_profiles"].find(profile_filt)
    }

    search_low = search.strip().lower() if search else None
    pairs: List[Tuple[MongoUser, MongoInstructorProfile]] = []
    for user in users:
        profile = profiles_by_uid.get(user.id)
        if not profile:
            continue
        if search_low:
            haystack = (
                f"{user.full_name} {profile.instructor_id} {user.email}".lower()
            )
            if search_low not in haystack:
                continue
        pairs.append((user, profile))

    pairs.sort(key=lambda pair: pair[1].registered_at, reverse=True)
    return pairs


def create_password_token(
    mongo_db: Database,
    *,
    user_id: int,
    token_hash: str,
    purpose: str,
    expires_at: datetime,
) -> MongoInstructorPasswordToken:
    now = datetime.now(timezone.utc)
    mongo_db["instructor_password_tokens"].update_many(
        {
            "user_id": int(user_id),
            "purpose": purpose,
            "used_at": None,
        },
        {"$set": {"used_at": now}},
    )
    token_id = next_sequence_id(mongo_db, "instructor_password_tokens")
    doc = {
        "id": token_id,
        "user_id": int(user_id),
        "token_hash": token_hash,
        "purpose": purpose,
        "expires_at": _ensure_utc(expires_at) or now,
        "used_at": None,
        "created_at": now,
    }
    mongo_db["instructor_password_tokens"].insert_one(doc)
    return MongoInstructorPasswordToken.from_doc(doc)


def find_unused_password_token(
    mongo_db: Database,
    token_hash: str,
) -> Optional[MongoInstructorPasswordToken]:
    doc = mongo_db["instructor_password_tokens"].find_one(
        {
            "token_hash": token_hash,
            "used_at": None,
            "purpose": {"$in": ["setup", "reset"]},
        }
    )
    return MongoInstructorPasswordToken.from_doc(doc) if doc else None


def claim_password_token(
    mongo_db: Database,
    token_id: int,
    now: datetime,
) -> bool:
    claimed = mongo_db["instructor_password_tokens"].find_one_and_update(
        {"id": int(token_id), "used_at": None},
        {"$set": {"used_at": _ensure_utc(now) or datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    return claimed is not None


# ---------------------------------------------------------------------------
# Transitional Phase 3A SQLite FK Shadow Sync
# Keeps SQLite foreign keys valid for non-migrated modules (courses,
# enrollments, quizzes, assignments, etc.) until Phases 3B/3C complete.
# ---------------------------------------------------------------------------


def sync_user_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    user: MongoUser,
    profile: Optional[MongoInstructorProfile] = None,
) -> None:
    """Mirror MongoDB user writes into SQLite during Phase 3A so unmigrated FKs hold."""
    if sqlite_db is None:
        return
    try:
        sql_user = sqlite_db.query(User).filter(User.id == user.id).first()
        if sql_user is None:
            sql_user = User(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                password_hash=user.password_hash,
                role=user.role,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
            sqlite_db.add(sql_user)
        else:
            sql_user.email = user.email
            sql_user.full_name = user.full_name
            sql_user.password_hash = user.password_hash
            sql_user.role = user.role
            sql_user.is_active = user.is_active
            sql_user.updated_at = user.updated_at

        if profile is not None:
            sql_prof = (
                sqlite_db.query(InstructorProfile)
                .filter(InstructorProfile.user_id == user.id)
                .first()
            )
            if sql_prof is None:
                id_taken = (
                    sqlite_db.query(InstructorProfile.id)
                    .filter(InstructorProfile.id == profile.id)
                    .first()
                    is not None
                )
                prof_kwargs: Dict[str, Any] = {
                    "user_id": profile.user_id,
                    "instructor_id": profile.instructor_id,
                    "phone_number": profile.phone_number,
                    "qualification": profile.qualification,
                    "department": profile.department,
                    "subject_expertise": profile.subject_expertise,
                    "experience_years": profile.experience_years,
                    "profile_photo_url": profile.profile_photo_url,
                    "registered_at": profile.registered_at,
                }
                if not id_taken:
                    prof_kwargs["id"] = profile.id
                sql_prof = InstructorProfile(**prof_kwargs)
                sqlite_db.add(sql_prof)
            else:
                sql_prof.instructor_id = profile.instructor_id
                sql_prof.phone_number = profile.phone_number
                sql_prof.qualification = profile.qualification
                sql_prof.department = profile.department
                sql_prof.subject_expertise = profile.subject_expertise
                sql_prof.experience_years = profile.experience_years
                sql_prof.profile_photo_url = profile.profile_photo_url

        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow sync failed for user_id=%s: %s", user.id, type(exc).__name__)
        raise


def restore_user_snapshot(mongo_db: Database, previous_user: MongoUser) -> None:
    """Compensating rollback for MongoDB `users` when a subsequent shadow sync fails."""
    mongo_db["users"].update_one(
        {"id": previous_user.id},
        {
            "$set": {
                "email": previous_user.email,
                "full_name": previous_user.full_name,
                "password_hash": previous_user.password_hash,
                "role": previous_user.role,
                "is_active": previous_user.is_active,
                "updated_at": previous_user.updated_at,
            }
        },
    )


def sync_or_rollback_user_shadow(
    mongo_db: Database,
    sqlite_db: Optional[Session],
    previous_user: MongoUser,
    updated_user: MongoUser,
    profile: Optional[MongoInstructorProfile] = None,
) -> None:
    """Sync updated user to SQLite shadow, restoring MongoDB snapshot on SQLite failure."""
    try:
        sync_user_to_sqlite_shadow(sqlite_db, updated_user, profile=profile)
    except Exception:
        restore_user_snapshot(mongo_db, previous_user)
        raise


def delete_user_from_sqlite_shadow(
    sqlite_db: Optional[Session],
    user_id: int,
) -> None:
    if sqlite_db is None:
        return
    try:
        sql_user = sqlite_db.query(User).filter(User.id == user_id).first()
        if sql_user is not None:
            sqlite_db.delete(sql_user)
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error("SQLite shadow delete failed for user_id=%s: %s", user_id, type(exc).__name__)
        raise


def sync_sqlite_users_to_mongo(
    sqlite_db: Session,
    mongo_db: Database,
) -> int:
    """Sync SQLite users & instructor_profiles into MongoDB (used by test fixture seeding)."""
    users = sqlite_db.query(User).order_by(User.id.asc()).all()
    max_user_id = 0
    for u in users:
        doc = {
            "id": int(u.id),
            "email": normalize_email(u.email),
            "full_name": u.full_name,
            "password_hash": u.password_hash,
            "role": u.role,
            "is_active": bool(u.is_active),
            "created_at": _ensure_utc(u.created_at) or datetime.now(timezone.utc),
            "updated_at": _ensure_utc(u.updated_at) or datetime.now(timezone.utc),
        }
        mongo_db["users"].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        if doc["id"] > max_user_id:
            max_user_id = doc["id"]
    sync_counter(mongo_db, "users", max_user_id)

    profiles = sqlite_db.query(InstructorProfile).order_by(InstructorProfile.id.asc()).all()
    max_prof_id = 0
    for p in profiles:
        pdoc = {
            "id": int(p.id),
            "user_id": int(p.user_id),
            "instructor_id": p.instructor_id,
            "phone_number": p.phone_number,
            "qualification": p.qualification,
            "department": p.department,
            "subject_expertise": p.subject_expertise,
            "experience_years": int(p.experience_years),
            "profile_photo_url": p.profile_photo_url,
            "registered_at": _ensure_utc(p.registered_at) or datetime.now(timezone.utc),
        }
        mongo_db["instructor_profiles"].update_one(
            {"id": pdoc["id"]}, {"$set": pdoc}, upsert=True
        )
        if pdoc["id"] > max_prof_id:
            max_prof_id = pdoc["id"]
    sync_counter(mongo_db, "instructor_profiles", max_prof_id)
    return len(users)
