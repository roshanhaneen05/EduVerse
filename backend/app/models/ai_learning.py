from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class AIQuiz(Base):
    __tablename__ = "ai_quizzes"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("course_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    difficulty = Column(String(20), nullable=False)
    question_type = Column(String(20), nullable=False)
    question_count = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="ck_ai_quizzes_difficulty"),
        CheckConstraint(
            "question_type IN ('mcq', 'true_false', 'short_answer', 'mixed')",
            name="ck_ai_quizzes_question_type",
        ),
        CheckConstraint("question_count IN (5, 10, 15, 20)", name="ck_ai_quizzes_question_count"),
    )

    student = relationship("User")
    course = relationship("Course")
    section = relationship("CourseSection")
    lesson = relationship("Lesson")
    questions = relationship(
        "AIQuizQuestion",
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="AIQuizQuestion.order_index",
    )
    attempts = relationship("AIQuizAttempt", back_populates="quiz", cascade="all, delete-orphan")


class AIQuizQuestion(Base):
    __tablename__ = "ai_quiz_questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("ai_quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(20), nullable=False)
    correct_answer = Column(Text, nullable=False)
    explanation = Column(Text, nullable=False)
    difficulty = Column(String(20), nullable=False)
    points = Column(Float, default=1.0, nullable=False)
    order_index = Column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "question_type IN ('mcq', 'true_false', 'short_answer')",
            name="ck_ai_quiz_questions_type",
        ),
        CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="ck_ai_quiz_questions_difficulty"),
        UniqueConstraint("quiz_id", "order_index", name="uq_ai_quiz_question_order"),
    )

    quiz = relationship("AIQuiz", back_populates="questions")
    options = relationship(
        "AIQuizOption",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="AIQuizOption.order_index",
    )


class AIQuizOption(Base):
    __tablename__ = "ai_quiz_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(
        Integer,
        ForeignKey("ai_quiz_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    option_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)
    order_index = Column(Integer, nullable=False)

    question = relationship("AIQuizQuestion", back_populates="options")


class AIQuizAttempt(Base):
    __tablename__ = "ai_quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("ai_quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    total_points = Column(Float, default=0.0, nullable=False)
    awarded_points = Column(Float, default=0.0, nullable=False)
    percentage = Column(Float, default=0.0, nullable=False)
    duration_seconds = Column(Integer, nullable=True)
    performance_level = Column(String(30), nullable=True)
    review_requested_at = Column(DateTime(timezone=True), nullable=True)

    quiz = relationship("AIQuiz", back_populates="attempts")
    student = relationship("User")
    answers = relationship(
        "AIQuizAnswer",
        back_populates="attempt",
        cascade="all, delete-orphan",
        order_by="AIQuizAnswer.id",
    )


class AIQuizAnswer(Base):
    __tablename__ = "ai_quiz_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("ai_quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("ai_quiz_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    selected_option_id = Column(Integer, ForeignKey("ai_quiz_options.id", ondelete="SET NULL"), nullable=True)
    answer_text = Column(Text, nullable=True)
    is_correct = Column(Boolean, default=False, nullable=False)
    awarded_points = Column(Float, default=0.0, nullable=False)
    automated_feedback = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_ai_quiz_attempt_question"),
    )

    attempt = relationship("AIQuizAttempt", back_populates="answers")
    question = relationship("AIQuizQuestion")
    selected_option = relationship("AIQuizOption")


class StudyPreference(Base):
    __tablename__ = "study_preferences"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    selected_course_ids = Column(JSON, nullable=False, default=list)
    deadlines_json = Column(JSON, nullable=False, default=list)
    available_hours_per_day = Column(Float, nullable=False, default=2.0)
    preferred_time = Column(String(20), nullable=False, default="evening")
    time_zone = Column(String(64), nullable=False, default="UTC")
    daily_duration_minutes = Column(Integer, nullable=False, default=30)
    target_completion_date = Column(Date, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    student = relationship("User")


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    selected_course_ids = Column(JSON, nullable=False, default=list)
    target_completion_date = Column(Date, nullable=False)
    available_hours_per_day = Column(Float, nullable=False)
    preferred_time = Column(String(20), nullable=False)
    time_zone = Column(String(64), nullable=False, default="UTC")
    daily_duration_minutes = Column(Integer, nullable=False)
    recommendations_json = Column(JSON, nullable=False, default=list)
    generation_mode = Column(String(12), nullable=False, default="ai")
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "generation_mode IN ('ai', 'rules')",
            name="ck_study_plans_generation_mode",
        ),
    )

    student = relationship("User")
    tasks = relationship("StudyTask", back_populates="plan", cascade="all, delete-orphan")
    deadlines = relationship("StudyDeadline", back_populates="plan", cascade="all, delete-orphan")


class StudyDeadline(Base):
    __tablename__ = "study_deadlines"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    deadline_type = Column(String(20), nullable=False)
    due_at = Column(DateTime(timezone=True), nullable=False)

    plan = relationship("StudyPlan", back_populates="deadlines")
    course = relationship("Course")


class StudyTask(Base):
    __tablename__ = "study_tasks"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("course_sections.id", ondelete="SET NULL"), nullable=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    starts_at = Column(DateTime(timezone=True), nullable=False, index=True)
    duration_minutes = Column(Integer, nullable=False)
    priority = Column(String(10), nullable=False)
    status = Column(String(12), nullable=False, default="pending", index=True)
    rationale = Column(Text, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("priority IN ('high', 'medium', 'low')", name="ck_study_tasks_priority"),
        CheckConstraint(
            "status IN ('pending', 'completed', 'missed')",
            name="ck_study_tasks_status",
        ),
        CheckConstraint("duration_minutes > 0", name="ck_study_tasks_duration"),
        UniqueConstraint("plan_id", "lesson_id", name="uq_study_plan_lesson"),
    )

    plan = relationship("StudyPlan", back_populates="tasks")
    student = relationship("User")
    course = relationship("Course")
    section = relationship("CourseSection")
    lesson = relationship("Lesson")


class StudyNotification(Base):
    __tablename__ = "study_notifications"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("study_tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    deadline_id = Column(Integer, ForeignKey("study_deadlines.id", ondelete="CASCADE"), nullable=True, index=True)
    notification_key = Column(String(100), nullable=False, unique=True, index=True)
    notification_type = Column(String(30), nullable=False)
    message = Column(Text, nullable=False)
    remind_at = Column(DateTime(timezone=True), nullable=False, index=True)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    student = relationship("User")
    task = relationship("StudyTask")
    deadline = relationship("StudyDeadline")
