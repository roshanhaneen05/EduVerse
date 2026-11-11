"""add enrollment approval and email delivery retry support

Revision ID: 8e4a6f2b1c90
Revises: d5a7c2e9f301
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8e4a6f2b1c90"
down_revision: Union[str, Sequence[str], None] = "d5a7c2e9f301"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("course_enrollments") as batch_op:
        batch_op.drop_constraint("ck_enrollment_status_valid", type_="check")
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("reviewed_by_instructor_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_course_enrollments_reviewed_by_instructor_id_users",
            "users",
            ["reviewed_by_instructor_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=30),
            server_default="pending",
            existing_nullable=False,
        )
    op.execute(
        "UPDATE course_enrollments SET status = 'approved' "
        "WHERE status IN ('active', 'completed')"
    )
    with op.batch_alter_table("course_enrollments") as batch_op:
        batch_op.create_check_constraint(
            "ck_enrollment_status_valid",
            "status IN ('pending', 'approved', 'rejected')",
        )

    op.create_table(
        "email_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enrollment_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            ["course_enrollments.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "enrollment_id",
            "event_type",
            name="uq_email_delivery_enrollment_event",
        ),
    )
    op.create_index(
        op.f("ix_email_deliveries_enrollment_id"),
        "email_deliveries",
        ["enrollment_id"],
        unique=False,
    )


def downgrade() -> None:
    reviewed_requests = op.get_bind().execute(
        sa.text(
            "SELECT COUNT(*) FROM course_enrollments "
            "WHERE status IN ('pending', 'rejected')"
        )
    ).scalar_one()
    if reviewed_requests:
        raise RuntimeError(
            "Cannot safely downgrade while pending or rejected enrollment requests exist."
        )

    op.drop_index(op.f("ix_email_deliveries_enrollment_id"), table_name="email_deliveries")
    op.drop_table("email_deliveries")

    with op.batch_alter_table("course_enrollments") as batch_op:
        batch_op.drop_constraint("ck_enrollment_status_valid", type_="check")

    op.execute(
        "UPDATE course_enrollments SET status = CASE "
        "WHEN completion_percentage >= 100.0 THEN 'completed' ELSE 'active' END "
        "WHERE status IN ('pending', 'approved', 'rejected')"
    )
    with op.batch_alter_table("course_enrollments") as batch_op:
        batch_op.create_check_constraint(
            "ck_enrollment_status_valid",
            "status IN ('active', 'completed')",
        )
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=30),
            server_default="active",
            existing_nullable=False,
        )
        batch_op.drop_constraint(
            "fk_course_enrollments_reviewed_by_instructor_id_users",
            type_="foreignkey",
        )
        batch_op.drop_column("reviewed_by_instructor_id")
        batch_op.drop_column("reviewed_at")
