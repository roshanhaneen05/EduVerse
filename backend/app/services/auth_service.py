from typing import Optional
from fastapi import HTTPException, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.models.user import UserRole
from app.repositories.user_repository import (
    MongoUser,
    create_user,
    delete_user_by_id,
    get_user_by_email,
    normalize_email,
    sync_user_to_sqlite_shadow,
)
from app.schemas.user import UserCreate
from app.security.password import (
    hash_password,
    validate_password_strength,
    verify_password,
)


def register_user(
    mongo_db: Database,
    user_in: UserCreate,
    sqlite_db: Optional[Session] = None,
) -> MongoUser:
    """
    Register a new user account in MongoDB (Student only via public endpoint).
    Prevents unauthorized privilege escalation: public registrations cannot be Admin or Instructor.
    """
    normalized_email = normalize_email(user_in.email)

    existing = get_user_by_email(mongo_db, normalized_email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    valid, message = validate_password_strength(user_in.password)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=message,
        )

    requested_role = (user_in.role or "student").strip().lower()
    if requested_role == UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Self-registration as Administrator is not permitted.",
        )
    elif requested_role == UserRole.INSTRUCTOR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Instructor accounts must be created by an administrator.",
        )
    else:
        assigned_role = UserRole.STUDENT.value

    hashed = hash_password(user_in.password)
    new_user = create_user(
        mongo_db,
        email=normalized_email,
        full_name=user_in.full_name.strip(),
        password_hash=hashed,
        role=assigned_role,
        is_active=True,
    )
    try:
        sync_user_to_sqlite_shadow(sqlite_db, new_user)
    except Exception:
        delete_user_by_id(mongo_db, new_user.id)
        raise
    return new_user


def register_student(
    mongo_db: Database,
    user_in: UserCreate,
    sqlite_db: Optional[Session] = None,
) -> MongoUser:
    """Backward-compatible wrapper for user registration."""
    return register_user(mongo_db, user_in, sqlite_db=sqlite_db)


def authenticate_user(
    mongo_db: Database,
    email: str,
    password: str,
) -> Optional[MongoUser]:
    """Verify credentials against MongoDB `users` and return user, or None."""
    user = get_user_by_email(mongo_db, email)
    if not user:
        return None
    if verify_password(password, user.password_hash):
        return user
    return None
