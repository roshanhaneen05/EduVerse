"""record whether study plans used AI or rules

Revision ID: a042e83c91f7
Revises: 7b2c4e6a9d10
Create Date: 2026-11-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a042e83c91f7"
down_revision: Union[str, Sequence[str], None] = "7b2c4e6a9d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("study_plans") as batch_op:
        batch_op.add_column(
            sa.Column("generation_mode", sa.String(length=12), nullable=False, server_default="ai"),
        )
        batch_op.create_check_constraint(
            "ck_study_plans_generation_mode",
            "generation_mode IN ('ai', 'rules')",
        )


def downgrade() -> None:
    with op.batch_alter_table("study_plans") as batch_op:
        batch_op.drop_constraint("ck_study_plans_generation_mode", type_="check")
        batch_op.drop_column("generation_mode")
