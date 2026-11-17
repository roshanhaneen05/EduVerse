"""add student-owned AI quizzes and study planner

Revision ID: 7b2c4e6a9d10
Revises: f36a2b17c90d
Create Date: 2026-11-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b2c4e6a9d10"
down_revision: Union[str, Sequence[str], None] = "f36a2b17c90d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_quizzes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("lesson_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("question_type", sa.String(length=20), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="ck_ai_quizzes_difficulty"),
        sa.CheckConstraint(
            "question_type IN ('mcq', 'true_false', 'short_answer', 'mixed')",
            name="ck_ai_quizzes_question_type",
        ),
        sa.CheckConstraint("question_count IN (5, 10, 15, 20)", name="ck_ai_quizzes_question_count"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["course_sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("student_id", "course_id", "section_id", "lesson_id"):
        op.create_index(f"ix_ai_quizzes_{column}", "ai_quizzes", [column])
    op.create_index("ix_ai_quizzes_id", "ai_quizzes", ["id"])

    op.create_table(
        "ai_quiz_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quiz_id", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(length=20), nullable=False),
        sa.Column("correct_answer", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("points", sa.Float(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "question_type IN ('mcq', 'true_false', 'short_answer')",
            name="ck_ai_quiz_questions_type",
        ),
        sa.CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="ck_ai_quiz_questions_difficulty"),
        sa.ForeignKeyConstraint(["quiz_id"], ["ai_quizzes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quiz_id", "order_index", name="uq_ai_quiz_question_order"),
    )
    op.create_index("ix_ai_quiz_questions_id", "ai_quiz_questions", ["id"])
    op.create_index("ix_ai_quiz_questions_quiz_id", "ai_quiz_questions", ["quiz_id"])

    op.create_table(
        "ai_quiz_options",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("option_text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["ai_quiz_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_quiz_options_id", "ai_quiz_options", ["id"])
    op.create_index("ix_ai_quiz_options_question_id", "ai_quiz_options", ["question_id"])

    op.create_table(
        "ai_quiz_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quiz_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_points", sa.Float(), nullable=False),
        sa.Column("awarded_points", sa.Float(), nullable=False),
        sa.Column("percentage", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("performance_level", sa.String(length=30), nullable=True),
        sa.Column("review_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["quiz_id"], ["ai_quizzes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_quiz_attempts_id", "ai_quiz_attempts", ["id"])
    op.create_index("ix_ai_quiz_attempts_quiz_id", "ai_quiz_attempts", ["quiz_id"])
    op.create_index("ix_ai_quiz_attempts_student_id", "ai_quiz_attempts", ["student_id"])

    op.create_table(
        "ai_quiz_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("selected_option_id", sa.Integer(), nullable=True),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("awarded_points", sa.Float(), nullable=False),
        sa.Column("automated_feedback", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["attempt_id"], ["ai_quiz_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["ai_quiz_questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["selected_option_id"], ["ai_quiz_options.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_ai_quiz_attempt_question"),
    )
    op.create_index("ix_ai_quiz_answers_id", "ai_quiz_answers", ["id"])
    op.create_index("ix_ai_quiz_answers_attempt_id", "ai_quiz_answers", ["attempt_id"])
    op.create_index("ix_ai_quiz_answers_question_id", "ai_quiz_answers", ["question_id"])

    op.create_table(
        "study_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("selected_course_ids", sa.JSON(), nullable=False),
        sa.Column("deadlines_json", sa.JSON(), nullable=False),
        sa.Column("available_hours_per_day", sa.Float(), nullable=False),
        sa.Column("preferred_time", sa.String(length=20), nullable=False),
        sa.Column("time_zone", sa.String(length=64), nullable=False),
        sa.Column("daily_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("target_completion_date", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id"),
    )
    op.create_index("ix_study_preferences_id", "study_preferences", ["id"])
    op.create_index("ix_study_preferences_student_id", "study_preferences", ["student_id"])

    op.create_table(
        "study_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("selected_course_ids", sa.JSON(), nullable=False),
        sa.Column("target_completion_date", sa.Date(), nullable=False),
        sa.Column("available_hours_per_day", sa.Float(), nullable=False),
        sa.Column("preferred_time", sa.String(length=20), nullable=False),
        sa.Column("time_zone", sa.String(length=64), nullable=False),
        sa.Column("daily_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("recommendations_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_study_plans_id", "study_plans", ["id"])
    op.create_index("ix_study_plans_student_id", "study_plans", ["student_id"])
    op.create_index("ix_study_plans_is_active", "study_plans", ["is_active"])

    op.create_table(
        "study_deadlines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("deadline_type", sa.String(length=20), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["study_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("plan_id", "student_id", "course_id"):
        op.create_index(f"ix_study_deadlines_{column}", "study_deadlines", [column])
    op.create_index("ix_study_deadlines_id", "study_deadlines", ["id"])

    op.create_table(
        "study_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("priority IN ('high', 'medium', 'low')", name="ck_study_tasks_priority"),
        sa.CheckConstraint("status IN ('pending', 'completed', 'missed')", name="ck_study_tasks_status"),
        sa.CheckConstraint("duration_minutes > 0", name="ck_study_tasks_duration"),
        sa.ForeignKeyConstraint(["plan_id"], ["study_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["course_sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "lesson_id", name="uq_study_plan_lesson"),
    )
    for column in ("plan_id", "student_id", "course_id", "lesson_id", "starts_at", "status"):
        op.create_index(f"ix_study_tasks_{column}", "study_tasks", [column])
    op.create_index("ix_study_tasks_id", "study_tasks", ["id"])

    op.create_table(
        "study_notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("deadline_id", sa.Integer(), nullable=True),
        sa.Column("notification_key", sa.String(length=100), nullable=False),
        sa.Column("notification_type", sa.String(length=30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["study_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deadline_id"], ["study_deadlines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notification_key"),
    )
    for column in ("student_id", "task_id", "deadline_id", "notification_key", "remind_at", "is_read"):
        op.create_index(f"ix_study_notifications_{column}", "study_notifications", [column])
    op.create_index("ix_study_notifications_id", "study_notifications", ["id"])


def downgrade() -> None:
    for column in ("student_id", "task_id", "deadline_id", "notification_key", "remind_at", "is_read"):
        op.drop_index(f"ix_study_notifications_{column}", table_name="study_notifications")
    op.drop_index("ix_study_notifications_id", table_name="study_notifications")
    op.drop_table("study_notifications")

    for column in ("plan_id", "student_id", "course_id", "lesson_id", "starts_at", "status"):
        op.drop_index(f"ix_study_tasks_{column}", table_name="study_tasks")
    op.drop_index("ix_study_tasks_id", table_name="study_tasks")
    op.drop_table("study_tasks")

    op.drop_index("ix_study_deadlines_course_id", table_name="study_deadlines")
    op.drop_index("ix_study_deadlines_student_id", table_name="study_deadlines")
    op.drop_index("ix_study_deadlines_plan_id", table_name="study_deadlines")
    op.drop_index("ix_study_deadlines_id", table_name="study_deadlines")
    op.drop_table("study_deadlines")

    op.drop_index("ix_study_plans_is_active", table_name="study_plans")
    op.drop_index("ix_study_plans_student_id", table_name="study_plans")
    op.drop_index("ix_study_plans_id", table_name="study_plans")
    op.drop_table("study_plans")

    op.drop_index("ix_study_preferences_student_id", table_name="study_preferences")
    op.drop_index("ix_study_preferences_id", table_name="study_preferences")
    op.drop_table("study_preferences")

    op.drop_index("ix_ai_quiz_answers_question_id", table_name="ai_quiz_answers")
    op.drop_index("ix_ai_quiz_answers_attempt_id", table_name="ai_quiz_answers")
    op.drop_index("ix_ai_quiz_answers_id", table_name="ai_quiz_answers")
    op.drop_table("ai_quiz_answers")

    op.drop_index("ix_ai_quiz_attempts_student_id", table_name="ai_quiz_attempts")
    op.drop_index("ix_ai_quiz_attempts_quiz_id", table_name="ai_quiz_attempts")
    op.drop_index("ix_ai_quiz_attempts_id", table_name="ai_quiz_attempts")
    op.drop_table("ai_quiz_attempts")

    op.drop_index("ix_ai_quiz_options_question_id", table_name="ai_quiz_options")
    op.drop_index("ix_ai_quiz_options_id", table_name="ai_quiz_options")
    op.drop_table("ai_quiz_options")

    op.drop_index("ix_ai_quiz_questions_quiz_id", table_name="ai_quiz_questions")
    op.drop_index("ix_ai_quiz_questions_id", table_name="ai_quiz_questions")
    op.drop_table("ai_quiz_questions")

    for column in ("student_id", "course_id", "section_id", "lesson_id"):
        op.drop_index(f"ix_ai_quizzes_{column}", table_name="ai_quizzes")
    op.drop_index("ix_ai_quizzes_id", table_name="ai_quizzes")
    op.drop_table("ai_quizzes")
