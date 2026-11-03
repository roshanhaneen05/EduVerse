from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("course_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    passing_score = Column(Integer, default=70, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)
    time_limit_minutes = Column(Integer, nullable=True)
    max_attempts = Column(Integer, default=3, nullable=False)
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
            "passing_score >= 0 AND passing_score <= 100",
            name="ck_quiz_passing_score_range",
        ),
        CheckConstraint(
            "time_limit_minutes IS NULL OR time_limit_minutes >= 1",
            name="ck_quiz_time_limit_positive",
        ),
        CheckConstraint(
            "max_attempts >= 0",
            name="ck_quiz_max_attempts_nonnegative",
        ),
    )

    # Relationships
    course = relationship("Course", back_populates="quizzes")
    section = relationship("CourseSection")
    lesson = relationship("Lesson")
    questions = relationship(
        "Question",
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="Question.order_index",
    )
    attempts = relationship("QuizAttempt", back_populates="quiz")

    def __repr__(self) -> str:
        return f"<Quiz id={self.id} title='{self.title}' passing_score={self.passing_score}%>"


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    order_index = Column(Integer, default=1, nullable=False)
    points = Column(Integer, default=1, nullable=False)

    __table_args__ = (
        CheckConstraint("order_index >= 1", name="ck_question_order_index_positive"),
        CheckConstraint("points >= 1", name="ck_question_points_positive"),
    )

    # Relationships
    quiz = relationship("Quiz", back_populates="questions")
    options = relationship(
        "AnswerOption",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="AnswerOption.id",
    )

    def __repr__(self) -> str:
        return f"<Question id={self.id} quiz_id={self.quiz_id} points={self.points}>"


class AnswerOption(Base):
    __tablename__ = "answer_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    option_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)
    order_index = Column(Integer, default=1, nullable=False)

    # Relationships
    question = relationship("Question", back_populates="options")

    def __repr__(self) -> str:
        return f"<AnswerOption id={self.id} question_id={self.question_id} is_correct={self.is_correct}>"


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="SET NULL"), nullable=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    score = Column(Float, nullable=False)  # Percentage, e.g. 85.0
    total_points = Column(Integer, default=0, nullable=False)
    passed = Column(Boolean, default=False, nullable=False)
    attempt_number = Column(Integer, default=1, nullable=False)
    is_completed = Column(Boolean, default=True, nullable=False)
    started_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    submitted_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    student = relationship("User", back_populates="quiz_attempts")
    quiz = relationship("Quiz", back_populates="attempts")
    answers = relationship("QuizAttemptAnswer", back_populates="attempt", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        if "user_id" in kwargs and "student_id" not in kwargs:
            kwargs["student_id"] = kwargs.pop("user_id")
        if "points_scored" in kwargs:
            kwargs.pop("points_scored")
        if "total_questions" in kwargs:
            kwargs.pop("total_questions")
        super().__init__(**kwargs)

    # Property alias for compatibility
    @property
    def user_id(self) -> int:
        return self.student_id

    @user_id.setter
    def user_id(self, value: int) -> None:
        self.student_id = value

    def __repr__(self) -> str:
        return f"<QuizAttempt id={self.id} student_id={self.student_id} quiz_id={self.quiz_id} score={self.score}%>"


class QuizAttemptAnswer(Base):
    __tablename__ = "quiz_attempt_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    selected_option_id = Column(Integer, ForeignKey("answer_options.id", ondelete="SET NULL"), nullable=True)
    is_correct = Column(Boolean, default=False, nullable=False)
    awarded_points = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question"),
    )

    # Relationships
    attempt = relationship("QuizAttempt", back_populates="answers")
    question = relationship("Question")
    selected_option = relationship("AnswerOption")

    def __repr__(self) -> str:
        return f"<QuizAttemptAnswer attempt_id={self.attempt_id} question_id={self.question_id} correct={self.is_correct}>"
