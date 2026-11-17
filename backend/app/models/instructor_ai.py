from datetime import datetime, timezone

from sqlalchemy import (
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


class AssignmentRubric(Base):
    __tablename__ = "assignment_rubrics"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(
        Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    expected_answer = Column(Text, nullable=False, default="")
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    assignment = relationship("Assignment")
    criteria = relationship(
        "EvaluationCriterionRubric",
        back_populates="rubric",
        cascade="all, delete-orphan",
        order_by="EvaluationCriterionRubric.order_index",
    )


class EvaluationCriterionRubric(Base):
    __tablename__ = "evaluation_criterion_rubrics"

    id = Column(Integer, primary_key=True, index=True)
    rubric_id = Column(
        Integer, ForeignKey("assignment_rubrics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    criterion_name = Column(String(255), nullable=False)
    maximum_marks = Column(Float, nullable=False)
    description = Column(Text, nullable=False)
    guidelines = Column(Text, nullable=False, default="")
    order_index = Column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("maximum_marks > 0", name="ck_rubric_criterion_marks_positive"),
        UniqueConstraint("rubric_id", "order_index", name="uq_rubric_criterion_order"),
    )

    rubric = relationship("AssignmentRubric", back_populates="criteria")


class AssignmentEvaluation(Base):
    __tablename__ = "assignment_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(
        Integer, ForeignKey("assignment_submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    instructor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_hash = Column(String(64), nullable=False)
    ai_suggested_marks = Column(Float, nullable=False)
    final_marks = Column(Float, nullable=True)
    ai_feedback = Column(Text, nullable=False)
    instructor_feedback = Column(Text, nullable=True)
    evaluation_status = Column(String(24), nullable=False, default="pending_review")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("ai_suggested_marks >= 0", name="ck_assignment_eval_ai_marks_nonnegative"),
        CheckConstraint("final_marks IS NULL OR final_marks >= 0", name="ck_assignment_eval_final_marks_nonnegative"),
        CheckConstraint(
            "evaluation_status IN ('pending_review', 'approved')",
            name="ck_assignment_evaluation_status",
        ),
    )

    submission = relationship("AssignmentSubmission")
    assignment = relationship("Assignment")
    student = relationship("User", foreign_keys=[student_id])
    instructor = relationship("User", foreign_keys=[instructor_id])
    criteria = relationship(
        "AssignmentEvaluationCriterion",
        back_populates="evaluation",
        cascade="all, delete-orphan",
        order_by="AssignmentEvaluationCriterion.order_index",
    )


class AssignmentEvaluationCriterion(Base):
    __tablename__ = "assignment_evaluation_criteria"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(
        Integer, ForeignKey("assignment_evaluations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    criterion_name = Column(String(255), nullable=False)
    maximum_marks = Column(Float, nullable=False)
    suggested_marks = Column(Float, nullable=False)
    final_marks = Column(Float, nullable=True)
    feedback = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("maximum_marks > 0", name="ck_eval_criterion_maximum_positive"),
        CheckConstraint("suggested_marks >= 0", name="ck_eval_criterion_suggested_nonnegative"),
        CheckConstraint("final_marks IS NULL OR final_marks >= 0", name="ck_eval_criterion_final_nonnegative"),
        UniqueConstraint("evaluation_id", "order_index", name="uq_eval_criterion_order"),
    )

    evaluation = relationship("AssignmentEvaluation", back_populates="criteria")


class QuestionPaper(Base):
    __tablename__ = "instructor_question_papers"

    id = Column(Integer, primary_key=True, index=True)
    instructor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    total_marks = Column(Float, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    difficulty = Column(String(16), nullable=False)
    section_ids_json = Column(JSON, nullable=False, default=list)
    lesson_ids_json = Column(JSON, nullable=False, default=list)
    exam_date = Column(Date, nullable=True)
    status = Column(String(12), nullable=False, default="draft")
    generation_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    published_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("total_marks > 0", name="ck_question_paper_total_marks_positive"),
        CheckConstraint("duration_minutes > 0", name="ck_question_paper_duration_positive"),
        CheckConstraint("difficulty IN ('easy', 'medium', 'hard', 'mixed')", name="ck_question_paper_difficulty"),
        CheckConstraint("status IN ('draft', 'published')", name="ck_question_paper_status"),
        UniqueConstraint("instructor_id", "generation_hash", name="uq_question_paper_generation_hash"),
    )

    instructor = relationship("User")
    course = relationship("Course")
    questions = relationship(
        "GeneratedQuestion",
        back_populates="paper",
        cascade="all, delete-orphan",
        order_by="GeneratedQuestion.question_order",
    )


class GeneratedQuestion(Base):
    __tablename__ = "instructor_generated_questions"

    id = Column(Integer, primary_key=True, index=True)
    question_paper_id = Column(
        Integer, ForeignKey("instructor_question_papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_text = Column(Text, nullable=False)
    question_type = Column(String(20), nullable=False)
    difficulty = Column(String(12), nullable=False)
    marks = Column(Float, nullable=False)
    options_json = Column(JSON, nullable=False, default=list)
    correct_answer = Column(Text, nullable=False)
    explanation = Column(Text, nullable=False)
    question_order = Column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("marks > 0", name="ck_generated_question_marks_positive"),
        CheckConstraint(
            "question_type IN ('mcq', 'true_false', 'short_answer', 'long_answer', 'fill_blank')",
            name="ck_generated_question_type",
        ),
        CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="ck_generated_question_difficulty"),
        UniqueConstraint("question_paper_id", "question_order", name="uq_generated_question_order"),
    )

    paper = relationship("QuestionPaper", back_populates="questions")
