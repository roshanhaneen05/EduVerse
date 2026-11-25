from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from pymongo.database import Database

from app.models.user import UserRole
from app.mongodb import get_mongo_db
from app.repositories.user_repository import MongoUser, get_user_by_id
from app.security.jwt import decode_access_token

security = HTTPBearer(auto_error=False)


def get_token_from_request(
    request: Request,
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """Extract token either from Authorization Bearer header or fallback auth_token cookie."""
    if auth_credentials:
        return auth_credentials.credentials
    cookie_token = request.cookies.get("auth_token")
    if cookie_token:
        return cookie_token
    return None


def get_current_user(
    token: Optional[str] = Depends(get_token_from_request),
    mongo_db: Database = Depends(get_mongo_db),
) -> MongoUser:
    """Retrieve and validate the currently authenticated user from MongoDB using JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (InvalidTokenError, ValueError):
        raise credentials_exception

    user = get_user_by_id(mongo_db, user_id)
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Contact an administrator.",
        )
    return user


def require_roles(*allowed_roles: str):
    """Callable dependency factory checking user role."""
    def role_checker(current_user: MongoUser = Depends(get_current_user)) -> MongoUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of roles [{', '.join(allowed_roles)}].",
            )
        return current_user
    return role_checker


def require_admin(current_user: MongoUser = Depends(get_current_user)) -> MongoUser:
    """Requires ADMIN role."""
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return current_user


def require_instructor(current_user: MongoUser = Depends(get_current_user)) -> MongoUser:
    """Requires INSTRUCTOR or ADMIN role."""
    if current_user.role not in (UserRole.INSTRUCTOR.value, UserRole.ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Instructor or administrator access required.",
        )
    return current_user


def require_student(current_user: MongoUser = Depends(get_current_user)) -> MongoUser:
    """Requires an active authenticated student."""
    if current_user.role != UserRole.STUDENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required.",
        )
    return current_user
