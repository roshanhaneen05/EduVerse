from fastapi import Depends
from pymongo.database import Database
from sqlalchemy.orm import Session
from app.database import get_db
from app.mongodb import get_mongo_db
from app.models.user import User
from app.security.rbac import (
    get_current_user,
    require_admin,
    require_instructor,
    require_roles,
    require_student,
)

__all__ = [
    "get_db",
    "get_mongo_db",
    "Depends",
    "Session",
    "Database",
    "User",
    "get_current_user",
    "require_admin",
    "require_instructor",
    "require_roles",
    "require_student",
]
