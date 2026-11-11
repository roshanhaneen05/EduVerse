from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import relationship
from app.database import Base


class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    enrolled_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completion_percentage = Column(Float, default=0.0, nullable=False)
    status = Column(String(30), default="pending", server_default=text("'pending'"), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by_instructor_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_student_course_enrollment"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_enrollment_status_valid",
        ),
        CheckConstraint(
            "completion_percentage >= 0.0 AND completion_percentage <= 100.0",
            name="ck_enrollment_completion_percentage",
        ),
    )

    # Relationships
    student = relationship("User", back_populates="enrollments", foreign_keys=[student_id])
    course = relationship("Course", back_populates="enrollments")

    def __init__(self, **kwargs):
        if "user_id" in kwargs and "student_id" not in kwargs:
            kwargs["student_id"] = kwargs.pop("user_id")
        if "progress_percentage" in kwargs and "completion_percentage" not in kwargs:
            kwargs["completion_percentage"] = kwargs.pop("progress_percentage")
        if "completed_at" in kwargs:
            kwargs.pop("completed_at")
        super().__init__(**kwargs)

    # Property alias for compatibility
    @property
    def user_id(self) -> int:
        return self.student_id

    @user_id.setter
    def user_id(self, value: int) -> None:
        self.student_id = value

    @property
    def progress_percentage(self) -> float:
        return self.completion_percentage

    @progress_percentage.setter
    def progress_percentage(self, value: float) -> None:
        self.completion_percentage = value

    def __repr__(self) -> str:
        return f"<CourseEnrollment student_id={self.student_id} course_id={self.course_id} completion={self.completion_percentage}%>"
