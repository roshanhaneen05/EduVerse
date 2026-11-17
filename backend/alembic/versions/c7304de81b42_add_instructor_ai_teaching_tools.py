"""add instructor AI assignment evaluation and question papers

Revision ID: c7304de81b42
Revises: a042e83c91f7
Create Date: 2026-11-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7304de81b42"
down_revision: Union[str, Sequence[str], None] = "a042e83c91f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assignment_rubrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id"),
    )
    op.create_index("ix_assignment_rubrics_id", "assignment_rubrics", ["id"])
    op.create_index("ix_assignment_rubrics_assignment_id", "assignment_rubrics", ["assignment_id"])

    op.create_table(
        "evaluation_criterion_rubrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rubric_id", sa.Integer(), nullable=False),
        sa.Column("criterion_name", sa.String(length=255), nullable=False),
        sa.Column("maximum_marks", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("guidelines", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.CheckConstraint("maximum_marks > 0", name="ck_rubric_criterion_marks_positive"),
        sa.ForeignKeyConstraint(["rubric_id"], ["assignment_rubrics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rubric_id", "order_index", name="uq_rubric_criterion_order"),
    )
    op.create_index("ix_evaluation_criterion_rubrics_id", "evaluation_criterion_rubrics", ["id"])
    op.create_index(
        "ix_evaluation_criterion_rubrics_rubric_id",
        "evaluation_criterion_rubrics",
        ["rubric_id"],
    )

    op.create_table(
        "assignment_evaluations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("instructor_id", sa.Integer(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("ai_suggested_marks", sa.Float(), nullable=False),
        sa.Column("final_marks", sa.Float(), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=False),
        sa.Column("instructor_feedback", sa.Text(), nullable=True),
        sa.Column("evaluation_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("ai_suggested_marks >= 0", name="ck_assignment_eval_ai_marks_nonnegative"),
        sa.CheckConstraint(
            "final_marks IS NULL OR final_marks >= 0",
            name="ck_assignment_eval_final_marks_nonnegative",
        ),
        sa.CheckConstraint(
            "evaluation_status IN ('pending_review', 'approved')",
            name="ck_assignment_evaluation_status",
        ),
        sa.ForeignKeyConstraint(["submission_id"], ["assignment_submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["instructor_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "submission_id", "assignment_id", "student_id", "instructor_id"):
        op.create_index(f"ix_assignment_evaluations_{column}", "assignment_evaluations", [column])

    op.create_table(
        "assignment_evaluation_criteria",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evaluation_id", sa.Integer(), nullable=False),
        sa.Column("criterion_name", sa.String(length=255), nullable=False),
        sa.Column("maximum_marks", sa.Float(), nullable=False),
        sa.Column("suggested_marks", sa.Float(), nullable=False),
        sa.Column("final_marks", sa.Float(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.CheckConstraint("maximum_marks > 0", name="ck_eval_criterion_maximum_positive"),
        sa.CheckConstraint("suggested_marks >= 0", name="ck_eval_criterion_suggested_nonnegative"),
        sa.CheckConstraint(
            "final_marks IS NULL OR final_marks >= 0",
            name="ck_eval_criterion_final_nonnegative",
        ),
        sa.ForeignKeyConstraint(["evaluation_id"], ["assignment_evaluations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_id", "order_index", name="uq_eval_criterion_order"),
    )
    op.create_index("ix_assignment_evaluation_criteria_id", "assignment_evaluation_criteria", ["id"])
    op.create_index(
        "ix_assignment_evaluation_criteria_evaluation_id",
        "assignment_evaluation_criteria",
        ["evaluation_id"],
    )

    op.create_table(
        "instructor_question_papers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instructor_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("total_marks", sa.Float(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("section_ids_json", sa.JSON(), nullable=False),
        sa.Column("lesson_ids_json", sa.JSON(), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("generation_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("total_marks > 0", name="ck_question_paper_total_marks_positive"),
        sa.CheckConstraint("duration_minutes > 0", name="ck_question_paper_duration_positive"),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard', 'mixed')",
            name="ck_question_paper_difficulty",
        ),
        sa.CheckConstraint("status IN ('draft', 'published')", name="ck_question_paper_status"),
        sa.ForeignKeyConstraint(["instructor_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instructor_id", "generation_hash", name="uq_question_paper_generation_hash"),
    )
    for column in ("id", "instructor_id", "course_id"):
        op.create_index(f"ix_instructor_question_papers_{column}", "instructor_question_papers", [column])

    op.create_table(
        "instructor_generated_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_paper_id", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(length=20), nullable=False),
        sa.Column("difficulty", sa.String(length=12), nullable=False),
        sa.Column("marks", sa.Float(), nullable=False),
        sa.Column("options_json", sa.JSON(), nullable=False),
        sa.Column("correct_answer", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("question_order", sa.Integer(), nullable=False),
        sa.CheckConstraint("marks > 0", name="ck_generated_question_marks_positive"),
        sa.CheckConstraint(
            "question_type IN ('mcq', 'true_false', 'short_answer', 'long_answer', 'fill_blank')",
            name="ck_generated_question_type",
        ),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_generated_question_difficulty",
        ),
        sa.ForeignKeyConstraint(["question_paper_id"], ["instructor_question_papers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_paper_id", "question_order", name="uq_generated_question_order"),
    )
    op.create_index("ix_instructor_generated_questions_id", "instructor_generated_questions", ["id"])
    op.create_index(
        "ix_instructor_generated_questions_question_paper_id",
        "instructor_generated_questions",
        ["question_paper_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_instructor_generated_questions_question_paper_id", table_name="instructor_generated_questions")
    op.drop_index("ix_instructor_generated_questions_id", table_name="instructor_generated_questions")
    op.drop_table("instructor_generated_questions")
    for column in ("id", "course_id", "instructor_id"):
        op.drop_index(f"ix_instructor_question_papers_{column}", table_name="instructor_question_papers")
    op.drop_table("instructor_question_papers")
    op.drop_index(
        "ix_assignment_evaluation_criteria_evaluation_id",
        table_name="assignment_evaluation_criteria",
    )
    op.drop_index("ix_assignment_evaluation_criteria_id", table_name="assignment_evaluation_criteria")
    op.drop_table("assignment_evaluation_criteria")
    for column in ("instructor_id", "student_id", "assignment_id", "submission_id", "id"):
        op.drop_index(f"ix_assignment_evaluations_{column}", table_name="assignment_evaluations")
    op.drop_table("assignment_evaluations")
    op.drop_index("ix_evaluation_criterion_rubrics_rubric_id", table_name="evaluation_criterion_rubrics")
    op.drop_index("ix_evaluation_criterion_rubrics_id", table_name="evaluation_criterion_rubrics")
    op.drop_table("evaluation_criterion_rubrics")
    op.drop_index("ix_assignment_rubrics_assignment_id", table_name="assignment_rubrics")
    op.drop_index("ix_assignment_rubrics_id", table_name="assignment_rubrics")
    op.drop_table("assignment_rubrics")
