from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, index=True)
    difficulty = Column(String(50), default="Beginner", nullable=False)
    is_published = Column(Boolean, default=False, nullable=False, index=True)
    instructor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
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

    # Relationships
    instructor = relationship("User", back_populates="courses")
    sections = relationship(
        "CourseSection",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="CourseSection.order_index",
    )
    lessons = relationship(
        "Lesson",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Lesson.order_index",
    )
    quizzes = relationship("Quiz", back_populates="course", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="course", cascade="all, delete-orphan")
    materials = relationship("LearningMaterial", back_populates="course", cascade="all, delete-orphan", order_by="LearningMaterial.created_at.desc()")
    enrollments = relationship("CourseEnrollment", back_populates="course", cascade="all, delete-orphan")
    announcements = relationship("CourseAnnouncement", back_populates="course", cascade="all, delete-orphan", order_by="CourseAnnouncement.created_at.desc()")
    discussions = relationship("CourseDiscussion", back_populates="course", cascade="all, delete-orphan", order_by="CourseDiscussion.created_at.desc()")

    def __init__(self, **kwargs):
        if "level" in kwargs and "difficulty" not in kwargs:
            kwargs["difficulty"] = kwargs.pop("level")
        if "slug" in kwargs:
            kwargs.pop("slug")
        if "short_description" in kwargs:
            kwargs.pop("short_description")
        if "thumbnail_url" in kwargs:
            kwargs.pop("thumbnail_url")
        super().__init__(**kwargs)

    # Property alias for compatibility
    @property
    def level(self) -> str:
        return self.difficulty

    @level.setter
    def level(self, value: str) -> None:
        self.difficulty = value

    def __repr__(self) -> str:
        return f"<Course id={self.id} title='{self.title}' difficulty='{self.difficulty}' published={self.is_published}>"
