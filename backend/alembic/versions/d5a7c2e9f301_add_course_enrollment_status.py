"""add persisted status to course enrollments

Revision ID: d5a7c2e9f301
Revises: a1c4901c0d13, c7e8a9101112
Create Date: 2026-03-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5a7c2e9f301"
down_revision: Union[str, Sequence[str], None] = ("a1c4901c0d13", "c7e8a9101112")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("course_enrollments") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(length=30), server_default="active", nullable=False)
        )
        batch_op.create_check_constraint(
            "ck_enrollment_status_valid",
            "status IN ('active', 'completed')",
        )
    op.execute(
        "UPDATE course_enrollments SET status = 'completed' "
        "WHERE completion_percentage >= 100.0"
    )


def downgrade() -> None:
    with op.batch_alter_table("course_enrollments") as batch_op:
        batch_op.drop_constraint("ck_enrollment_status_valid", type_="check")
        batch_op.drop_column("status")
