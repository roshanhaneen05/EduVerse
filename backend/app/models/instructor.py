from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class InstructorProfile(Base):
    __tablename__ = "instructor_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    instructor_id = Column(String(32), nullable=False, unique=True, index=True)
    phone_number = Column(String(30), nullable=False, default="")
    qualification = Column(String(150), nullable=False, default="")
    department = Column(String(150), nullable=False, default="")
    subject_expertise = Column(String(255), nullable=False, default="")
    experience_years = Column(Integer, nullable=False, default=0)
    profile_photo_url = Column(String(500), nullable=True)
    registered_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="instructor_profile")


class InstructorPasswordToken(Base):
    __tablename__ = "instructor_password_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    purpose = Column(String(20), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
