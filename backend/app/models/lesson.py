from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("course_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    video_url = Column(String(500), nullable=True)
    video_storage_key = Column(String(255), nullable=True)
    order_index = Column(Integer, default=1, nullable=False)
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
        CheckConstraint("order_index >= 1", name="ck_lesson_order_index_positive"),
    )

    # Relationships
    course = relationship("Course", back_populates="lessons")
    section = relationship("CourseSection", back_populates="lessons")
    progress_records = relationship("LessonProgress", back_populates="lesson", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        if "duration_minutes" in kwargs:
            kwargs.pop("duration_minutes")
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<Lesson id={self.id} course_id={self.course_id} title='{self.title}'>"


class LessonProgress(Base):
    __tablename__ = "lesson_progress"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    is_completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("student_id", "lesson_id", name="uq_student_lesson_progress"),
    )

    # Relationships
    student = relationship("User", back_populates="lesson_progress")
    lesson = relationship("Lesson", back_populates="progress_records")

    def __init__(self, **kwargs):
        if "user_id" in kwargs and "student_id" not in kwargs:
            kwargs["student_id"] = kwargs.pop("user_id")
        super().__init__(**kwargs)

    # Property alias for compatibility
    @property
    def user_id(self) -> int:
        return self.student_id

    @user_id.setter
    def user_id(self, value: int) -> None:
        self.student_id = value

    def __repr__(self) -> str:
        return f"<LessonProgress student_id={self.student_id} lesson_id={self.lesson_id} completed={self.is_completed}>"
