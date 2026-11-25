import hashlib
import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import get_db, get_mongo_db, require_admin
from app.models.user import UserRole
from app.repositories.course_repository import (
    get_course_by_id,
    instructor_has_courses,
    restore_course_snapshot,
    sync_course_to_sqlite_shadow,
    update_course_doc,
)
from app.repositories.user_repository import (
    MongoInstructorProfile,
    MongoUser,
    allocate_instructor_code,
    create_instructor_profile,
    create_password_token,
    create_user,
    delete_user_by_id,
    delete_user_from_sqlite_shadow,
    email_exists_for_other_user,
    get_instructor_profile_by_user_id,
    get_user_by_email,
    get_user_by_id,
    list_instructors_filtered,
    normalize_email,
    sync_or_rollback_user_shadow,
    sync_user_to_sqlite_shadow,
    update_instructor_profile_fields,
    update_user_fields,
)
from app.schemas.common import MessageResponse
from app.schemas.instructor import (
    CourseInstructorAssignment,
    InstructorCreate,
    InstructorCreatedResponse,
    InstructorResponse,
    InstructorStatusUpdate,
    InstructorUpdate,
)
from app.security.password import hash_password
from app.services.email_service import (
    EmailNotConfiguredError,
    send_instructor_password_email,
    send_instructor_status_email,
)

router = APIRouter(prefix="/admin", tags=["Administrator Instructor Management"])
logger = logging.getLogger(__name__)
settings = get_settings()


def _serialize_instructor(user: MongoUser, profile: MongoInstructorProfile) -> InstructorResponse:
    return InstructorResponse(
        user_id=user.id,
        instructor_id=profile.instructor_id,
        full_name=user.full_name,
        email=user.email,
        phone_number=profile.phone_number,
        qualification=profile.qualification,
        department=profile.department,
        subject_expertise=profile.subject_expertise,
        experience_years=profile.experience_years,
        profile_photo_url=profile.profile_photo_url,
        is_active=user.is_active,
        registered_at=profile.registered_at,
    )


def _issue_password_link(
    mongo_db: Database,
    user: MongoUser,
    purpose: str,
) -> str:
    raw_token = secrets.token_urlsafe(40)
    create_password_token(
        mongo_db,
        user_id=user.id,
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        purpose=purpose,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/instructor/setup-password?token={raw_token}"


def _send_password_email(
    user: MongoUser,
    profile: MongoInstructorProfile,
    setup_link: str,
    purpose: str,
) -> str:
    try:
        send_instructor_password_email(user, profile, setup_link, settings, purpose)
        return "sent"
    except EmailNotConfiguredError:
        logger.warning("Instructor password email for user %s was not sent: SMTP is not configured.", user.id)
        return "not_configured"
    except (smtplib.SMTPException, OSError, ValueError):
        logger.exception("Instructor password email for user %s failed.", user.id)
        return "failed"


def _send_status_email(user: MongoUser, profile: MongoInstructorProfile) -> str:
    try:
        send_instructor_status_email(user, profile, settings)
        return "sent"
    except EmailNotConfiguredError:
        logger.warning("Instructor status email for user %s was not sent: SMTP is not configured.", user.id)
        return "not_configured"
    except (smtplib.SMTPException, OSError, ValueError):
        logger.exception("Instructor status email for user %s failed.", user.id)
        return "failed"


@router.get(
    "/instructors",
    response_model=List[InstructorResponse],
    summary="Search and filter registered instructors",
)
def list_instructors(
    search: Optional[str] = Query(default=None, max_length=100),
    department: Optional[str] = Query(default=None, max_length=150),
    is_active: Optional[bool] = None,
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    pairs = list_instructors_filtered(
        mongo_db,
        search=search,
        department=department,
        is_active=is_active,
    )
    return [_serialize_instructor(user, profile) for user, profile in pairs]


@router.post(
    "/instructors",
    response_model=InstructorCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an instructor account and email a secure password setup link",
)
def create_instructor(
    payload: InstructorCreate,
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    normalized_email = normalize_email(str(payload.email))
    if get_user_by_email(mongo_db, normalized_email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    user = create_user(
        mongo_db,
        full_name=payload.full_name.strip(),
        email=normalized_email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role=UserRole.INSTRUCTOR.value,
        is_active=True,
    )
    try:
        profile = create_instructor_profile(
            mongo_db,
            user_id=user.id,
            instructor_id=allocate_instructor_code(mongo_db),
            phone_number=payload.phone_number.strip(),
            qualification=payload.qualification.strip(),
            department=payload.department.strip(),
            subject_expertise=payload.subject_expertise.strip(),
            experience_years=payload.experience_years,
            profile_photo_url=payload.profile_photo_url.strip() if payload.profile_photo_url else None,
            registered_at=user.created_at,
        )
        setup_link = _issue_password_link(mongo_db, user, "setup")
        sync_user_to_sqlite_shadow(db, user, profile=profile)
    except Exception:
        delete_user_by_id(mongo_db, user.id)
        raise

    email_status = _send_password_email(user, profile, setup_link, "setup")
    response = _serialize_instructor(user, profile)
    return InstructorCreatedResponse(
        **response.model_dump(),
        email_delivery_status=email_status,
    )


@router.get(
    "/instructors/{user_id}",
    response_model=InstructorResponse,
    summary="View instructor profile details",
)
def get_instructor(
    user_id: int,
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    user = get_user_by_id(mongo_db, user_id)
    profile = get_instructor_profile_by_user_id(mongo_db, user_id) if user else None
    if not user or user.role != UserRole.INSTRUCTOR.value or not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found.")
    return _serialize_instructor(user, profile)


@router.put(
    "/instructors/{user_id}",
    response_model=InstructorResponse,
    summary="Update instructor contact and academic profile",
)
def update_instructor(
    user_id: int,
    payload: InstructorUpdate,
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    user = get_user_by_id(mongo_db, user_id)
    profile = get_instructor_profile_by_user_id(mongo_db, user_id) if user else None
    if not user or user.role != UserRole.INSTRUCTOR.value or not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found.")

    updates = payload.model_dump(exclude_unset=True)
    user_updates: dict = {}
    if "email" in updates and updates["email"] is not None:
        normalized_email = normalize_email(str(updates["email"]))
        if email_exists_for_other_user(mongo_db, normalized_email, exclude_user_id=user.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )
        user_updates["email"] = normalized_email
    if "full_name" in updates and updates["full_name"] is not None:
        user_updates["full_name"] = updates.pop("full_name").strip()
    else:
        updates.pop("full_name", None)
    updates.pop("email", None)

    profile_updates = {
        field: value.strip() if isinstance(value, str) else value
        for field, value in updates.items()
    }
    updated_user = update_user_fields(mongo_db, user.id, user_updates) if user_updates else user
    updated_profile = (
        update_instructor_profile_fields(mongo_db, user.id, profile_updates)
        if profile_updates
        else profile
    )
    if updated_user is None or updated_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found.")

    sync_or_rollback_user_shadow(mongo_db, db, user, updated_user, profile=updated_profile)
    return _serialize_instructor(updated_user, updated_profile)


@router.patch(
    "/instructors/{user_id}/status",
    response_model=InstructorCreatedResponse,
    summary="Activate or deactivate an instructor account",
)
def update_instructor_status(
    user_id: int,
    payload: InstructorStatusUpdate,
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    user = get_user_by_id(mongo_db, user_id)
    profile = get_instructor_profile_by_user_id(mongo_db, user_id) if user else None
    if not user or user.role != UserRole.INSTRUCTOR.value or not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found.")

    changed = user.is_active != payload.is_active
    updated_user = update_user_fields(mongo_db, user.id, {"is_active": payload.is_active})
    if updated_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found.")

    sync_or_rollback_user_shadow(mongo_db, db, user, updated_user, profile=profile)
    email_status = _send_status_email(updated_user, profile) if changed else "not_needed"
    response = _serialize_instructor(updated_user, profile)
    return InstructorCreatedResponse(
        **response.model_dump(),
        email_delivery_status=email_status,
    )


@router.post(
    "/instructors/{user_id}/password-reset",
    response_model=MessageResponse,
    summary="Send an instructor a single-use password reset link",
)
def reset_instructor_password(
    user_id: int,
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    user = get_user_by_id(mongo_db, user_id)
    profile = get_instructor_profile_by_user_id(mongo_db, user_id) if user else None
    if not user or user.role != UserRole.INSTRUCTOR.value or not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found.")
    setup_link = _issue_password_link(mongo_db, user, "reset")
    email_status = _send_password_email(user, profile, setup_link, "reset")
    return MessageResponse(message=f"Password reset email status: {email_status}.")


@router.delete(
    "/instructors/{user_id}",
    response_model=MessageResponse,
    summary="Delete an instructor account after its courses are reassigned",
)
def delete_instructor(
    user_id: int,
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    user = get_user_by_id(mongo_db, user_id)
    profile = get_instructor_profile_by_user_id(mongo_db, user_id) if user else None
    if not user or user.role != UserRole.INSTRUCTOR.value or not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found.")
    if instructor_has_courses(mongo_db, user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reassign this instructor's courses before deleting the account.",
        )
    delete_user_by_id(mongo_db, user_id)
    delete_user_from_sqlite_shadow(db, user_id)
    return MessageResponse(message="Instructor account deleted.")


@router.put(
    "/courses/{course_id}/instructor",
    response_model=MessageResponse,
    summary="Assign a course to a registered instructor",
)
def assign_course_instructor(
    course_id: int,
    assignment: CourseInstructorAssignment,
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    instructor = get_user_by_id(mongo_db, assignment.instructor_user_id)
    profile = (
        get_instructor_profile_by_user_id(mongo_db, instructor.id)
        if instructor
        else None
    )
    if (
        not instructor
        or not profile
        or instructor.role != UserRole.INSTRUCTOR.value
        or not instructor.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active registered instructor not found.",
        )
    updated_course = update_course_doc(mongo_db, course.id, {"instructor_id": instructor.id})
    if not updated_course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    try:
        sync_user_to_sqlite_shadow(db, instructor, profile=profile)
        sync_course_to_sqlite_shadow(db, updated_course)
    except Exception:
        restore_course_snapshot(mongo_db, course)
        raise
    return MessageResponse(message="Course assigned to instructor.")
    return MessageResponse(message="Course assigned to instructor.")


