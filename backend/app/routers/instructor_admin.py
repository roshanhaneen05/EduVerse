import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
import hashlib
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.dependencies import get_db, require_admin
from app.models.course import Course
from app.models.instructor import InstructorPasswordToken, InstructorProfile
from app.models.user import User, UserRole
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


def _serialize_instructor(user: User, profile: InstructorProfile) -> InstructorResponse:
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


def _new_instructor_id(db: Session) -> str:
    for _ in range(5):
        candidate = f"EV-I-{secrets.token_hex(4).upper()}"
        if not db.query(InstructorProfile.id).filter(
            InstructorProfile.instructor_id == candidate
        ).first():
            return candidate
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Unable to allocate an instructor ID. Please try again.",
    )


def _issue_password_link(
    db: Session,
    user: User,
    purpose: str,
) -> str:
    db.query(InstructorPasswordToken).filter(
        InstructorPasswordToken.user_id == user.id,
        InstructorPasswordToken.purpose == purpose,
        InstructorPasswordToken.used_at.is_(None),
    ).update({"used_at": datetime.now(timezone.utc)}, synchronize_session=False)
    raw_token = secrets.token_urlsafe(40)
    db.add(
        InstructorPasswordToken(
            user_id=user.id,
            token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            purpose=purpose,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/instructor/setup-password?token={raw_token}"


def _send_password_email(
    user: User,
    profile: InstructorProfile,
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


def _send_status_email(user: User, profile: InstructorProfile) -> str:
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
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = (
        db.query(User, InstructorProfile)
        .join(InstructorProfile, InstructorProfile.user_id == User.id)
        .filter(User.role == UserRole.INSTRUCTOR.value)
    )
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            (User.full_name.ilike(pattern))
            | (InstructorProfile.instructor_id.ilike(pattern))
            | (User.email.ilike(pattern))
        )
    if department:
        query = query.filter(InstructorProfile.department.ilike(f"%{department.strip()}%"))
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    return [
        _serialize_instructor(user, profile)
        for user, profile in query.order_by(InstructorProfile.registered_at.desc()).all()
    ]


@router.post(
    "/instructors",
    response_model=InstructorCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an instructor account and email a secure password setup link",
)
def create_instructor(
    payload: InstructorCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    normalized_email = str(payload.email).strip().lower()
    if db.query(User.id).filter(User.email.ilike(normalized_email)).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    user = User(
        full_name=payload.full_name.strip(),
        email=normalized_email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role=UserRole.INSTRUCTOR.value,
        is_active=True,
    )
    profile = InstructorProfile(
        instructor_id=_new_instructor_id(db),
        phone_number=payload.phone_number.strip(),
        qualification=payload.qualification.strip(),
        department=payload.department.strip(),
        subject_expertise=payload.subject_expertise.strip(),
        experience_years=payload.experience_years,
        profile_photo_url=payload.profile_photo_url.strip() if payload.profile_photo_url else None,
    )
    user.instructor_profile = profile
    db.add(user)
    try:
        db.flush()
        setup_link = _issue_password_link(db, user, "setup")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.info("Instructor account creation conflicted with a unique database constraint.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The email address or generated instructor ID is already in use. Please try again.",
        ) from exc
    db.refresh(user)
    db.refresh(profile)
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
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    record = (
        db.query(User, InstructorProfile)
        .join(InstructorProfile, InstructorProfile.user_id == User.id)
        .filter(User.id == user_id, User.role == UserRole.INSTRUCTOR.value)
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found.")
    return _serialize_instructor(*record)


@router.put(
    "/instructors/{user_id}",
    response_model=InstructorResponse,
    summary="Update instructor contact and academic profile",
)
def update_instructor(
    user_id: int,
    payload: InstructorUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.INSTRUCTOR.value).first()
    if not user or not user.instructor_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found.")

    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"] is not None:
        normalized_email = str(updates["email"]).strip().lower()
        duplicate = db.query(User.id).filter(
            User.email.ilike(normalized_email),
            User.id != user.id,
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )
        user.email = normalized_email
    if "full_name" in updates and updates["full_name"] is not None:
        user.full_name = updates.pop("full_name").strip()
    else:
        updates.pop("full_name", None)
    updates.pop("email", None)
    for field, value in updates.items():
        setattr(user.instructor_profile, field, value.strip() if isinstance(value, str) else value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The email address is already in use.",
        ) from exc
    db.refresh(user)
    db.refresh(user.instructor_profile)
    return _serialize_instructor(user, user.instructor_profile)


@router.patch(
    "/instructors/{user_id}/status",
    response_model=InstructorCreatedResponse,
    summary="Activate or deactivate an instructor account",
)
def update_instructor_status(
    user_id: int,
    payload: InstructorStatusUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.INSTRUCTOR.value).first()
    if not user or not user.instructor_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found.")
    changed = user.is_active != payload.is_active
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    email_status = _send_status_email(user, user.instructor_profile) if changed else "not_needed"
    response = _serialize_instructor(user, user.instructor_profile)
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
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .options(joinedload(User.instructor_profile))
        .filter(User.id == user_id, User.role == UserRole.INSTRUCTOR.value)
        .first()
    )
    if not user or not user.instructor_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found.")
    setup_link = _issue_password_link(db, user, "reset")
    db.commit()
    email_status = _send_password_email(user, user.instructor_profile, setup_link, "reset")
    return MessageResponse(message=f"Password reset email status: {email_status}.")


@router.delete(
    "/instructors/{user_id}",
    response_model=MessageResponse,
    summary="Delete an instructor account after its courses are reassigned",
)
def delete_instructor(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.INSTRUCTOR.value).first()
    if not user or not user.instructor_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found.")
    if db.query(Course.id).filter(Course.instructor_id == user_id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reassign this instructor's courses before deleting the account.",
        )
    db.delete(user)
    db.commit()
    return MessageResponse(message="Instructor account deleted.")


@router.put(
    "/courses/{course_id}/instructor",
    response_model=MessageResponse,
    summary="Assign a course to a registered instructor",
)
def assign_course_instructor(
    course_id: int,
    assignment: CourseInstructorAssignment,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    instructor = (
        db.query(User)
        .join(InstructorProfile, InstructorProfile.user_id == User.id)
        .filter(
            User.id == assignment.instructor_user_id,
            User.role == UserRole.INSTRUCTOR.value,
            User.is_active.is_(True),
        )
        .first()
    )
    if not instructor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active registered instructor not found.",
        )
    course.instructor_id = instructor.id
    db.commit()
    return MessageResponse(message="Course assigned to instructor.")


