import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import get_current_user, get_db, get_mongo_db
from app.models.user import UserRole
from app.repositories.user_repository import (
    MongoUser,
    claim_password_token,
    find_unused_password_token,
    get_instructor_profile_by_user_id,
    get_user_by_id,
    sync_or_rollback_user_shadow,
    update_user_fields,
)
from app.schemas.auth import TokenResponse
from app.schemas.common import MessageResponse
from app.schemas.user import (
    InstructorPasswordSetup,
    PasswordChange,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdateProfile,
)
from app.security.jwt import create_access_token
from app.security.password import (
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.security.rate_limiter import check_rate_limit
from app.services.auth_service import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["Authentication & Profile"])
settings = get_settings()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student account",
)
def register(
    user_in: UserCreate,
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    user = register_user(mongo_db, user_in, sqlite_db=db)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive JWT access token",
)
def login(
    login_data: UserLogin,
    request: Request,
    response: Response,
    mongo_db: Database = Depends(get_mongo_db),
):
    check_rate_limit(request, limit=15, window_seconds=60, key_prefix="login")
    user = authenticate_user(mongo_db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact an administrator.",
        )

    # Create JWT
    token_payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name,
    }
    access_token = create_access_token(token_payload)

    # Set secure HttpOnly cookie (with SameSite=Lax for standard browser security)
    response.set_cookie(
        key="auth_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 if login_data.remember_me else None,
        samesite="lax",
        secure=settings.is_production,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/instructor-login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate an instructor account",
)
def instructor_login(
    login_data: UserLogin,
    request: Request,
    response: Response,
    mongo_db: Database = Depends(get_mongo_db),
):
    check_rate_limit(request, limit=15, window_seconds=60, key_prefix="login")
    user = authenticate_user(mongo_db, login_data.email, login_data.password)
    profile = (
        get_instructor_profile_by_user_id(mongo_db, user.id)
        if user
        else None
    )
    if not user or user.role != UserRole.INSTRUCTOR.value or not profile:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid instructor email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact an administrator.",
        )

    access_token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
        }
    )
    response.set_cookie(
        key="auth_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 if login_data.remember_me else None,
        samesite="lax",
        secure=settings.is_production,
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/instructor-password",
    response_model=MessageResponse,
    summary="Set or reset an instructor password using a single-use email token",
)
def set_instructor_password(
    payload: InstructorPasswordSetup,
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    valid, message = validate_password_strength(payload.new_password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)

    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    token_record = find_unused_password_token(mongo_db, token_hash)
    now = datetime.now(timezone.utc)
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password link is invalid or has expired. Contact an administrator for a new link.",
        )
    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password link is invalid or has expired. Contact an administrator for a new link.",
        )

    user = get_user_by_id(mongo_db, token_record.user_id)
    if not user or user.role != UserRole.INSTRUCTOR.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid instructor password link.")

    if not claim_password_token(mongo_db, token_record.id, now):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password link has already been used.",
        )
    updated_user = update_user_fields(
        mongo_db,
        user.id,
        {"password_hash": hash_password(payload.new_password)},
    )
    if updated_user:
        sync_or_rollback_user_shadow(mongo_db, db, user, updated_user)
    return MessageResponse(message="Your instructor password has been set successfully.")


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Log out and clear session cookie",
)
def logout(response: Response):
    response.delete_cookie(key="auth_token")
    return MessageResponse(message="Successfully logged out.")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
def get_me(current_user: MongoUser = Depends(get_current_user)):
    return current_user


@router.put(
    "/profile",
    response_model=UserResponse,
    summary="Update personal profile information",
)
def update_profile(
    profile_data: UserUpdateProfile,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    if profile_data.full_name is not None:
        updated = update_user_fields(
            mongo_db,
            current_user.id,
            {"full_name": profile_data.full_name.strip()},
        )
        if updated:
            sync_or_rollback_user_shadow(mongo_db, db, current_user, updated)
            return updated
    return current_user


@router.put(
    "/password",
    response_model=MessageResponse,
    summary="Change user password",
)
def change_password(
    pwd_data: PasswordChange,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    if not verify_password(pwd_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    valid, message = validate_password_strength(pwd_data.new_password)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=message,
        )

    updated = update_user_fields(
        mongo_db,
        current_user.id,
        {"password_hash": hash_password(pwd_data.new_password)},
    )
    if updated:
        sync_or_rollback_user_shadow(mongo_db, db, current_user, updated)
    return MessageResponse(message="Password successfully updated.")
