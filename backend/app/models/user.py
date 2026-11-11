import enum
from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base


class UserRole(str, enum.Enum):
    STUDENT = "student"
    INSTRUCTOR = "instructor"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default=UserRole.STUDENT.value, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('student', 'instructor', 'admin')",
            name="ck_users_role_valid",
        ),
    )

    # Relationships
    courses = relationship("Course", back_populates="instructor", cascade="all, delete-orphan")
    enrollments = relationship(
        "CourseEnrollment",
        back_populates="student",
        foreign_keys="CourseEnrollment.student_id",
        cascade="all, delete-orphan",
    )
    lesson_progress = relationship("LessonProgress", back_populates="student", cascade="all, delete-orphan")
    quiz_attempts = relationship("QuizAttempt", back_populates="student")
    assignment_submissions = relationship(
        "AssignmentSubmission",
        foreign_keys="AssignmentSubmission.student_id",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    ai_conversations = relationship("AIConversation", back_populates="user", cascade="all, delete-orphan")
    uploaded_materials = relationship("LearningMaterial", back_populates="uploader", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan", order_by="Notification.created_at.desc()")

    def __init__(self, **kwargs):
        if "hashed_password" in kwargs and "password_hash" not in kwargs:
            kwargs["password_hash"] = kwargs.pop("hashed_password")
        if "bio" in kwargs:
            kwargs.pop("bio")
        if "avatar_url" in kwargs:
            kwargs.pop("avatar_url")
        super().__init__(**kwargs)

    # Property alias for compatibility
    @property
    def hashed_password(self) -> str:
        return self.password_hash

    @hashed_password.setter
    def hashed_password(self, value: str) -> None:
        self.password_hash = value

    def __repr__(self) -> str:
        return f"<User id={self.id} email='{self.email}' role='{self.role}'>"
