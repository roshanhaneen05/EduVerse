"""add admin-managed instructor profiles and password setup tokens

Revision ID: f36a2b17c90d
Revises: 8e4a6f2b1c90
Create Date: 2026-11-14
"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f36a2b17c90d"
down_revision: Union[str, Sequence[str], None] = "8e4a6f2b1c90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "instructor_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("instructor_id", sa.String(length=32), nullable=False),
        sa.Column("phone_number", sa.String(length=30), server_default="", nullable=False),
        sa.Column("qualification", sa.String(length=150), server_default="", nullable=False),
        sa.Column("department", sa.String(length=150), server_default="", nullable=False),
        sa.Column("subject_expertise", sa.String(length=255), server_default="", nullable=False),
        sa.Column("experience_years", sa.Integer(), server_default="0", nullable=False),
        sa.Column("profile_photo_url", sa.String(length=500), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_instructor_profiles_user_id"),
        sa.UniqueConstraint("instructor_id", name="uq_instructor_profiles_instructor_id"),
    )
    op.create_index("ix_instructor_profiles_user_id", "instructor_profiles", ["user_id"])
    op.create_index("ix_instructor_profiles_instructor_id", "instructor_profiles", ["instructor_id"])

    existing_instructors = op.get_bind().execute(
        sa.text("SELECT id, created_at FROM users WHERE role = 'instructor'")
    ).fetchall()
    for user_id, created_at in existing_instructors:
        op.get_bind().execute(
            sa.text(
                "INSERT INTO instructor_profiles "
                "(user_id, instructor_id, registered_at) "
                "VALUES (:user_id, :instructor_id, :registered_at)"
            ),
            {
                "user_id": user_id,
                "instructor_id": f"EV-I-LEGACY-{user_id}",
                "registered_at": created_at or datetime.now(timezone.utc),
            },
        )

    op.create_table(
        "instructor_password_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_instructor_password_tokens_token_hash"),
    )
    op.create_index("ix_instructor_password_tokens_user_id", "instructor_password_tokens", ["user_id"])
    op.create_index("ix_instructor_password_tokens_token_hash", "instructor_password_tokens", ["token_hash"])


def downgrade() -> None:
    op.drop_index("ix_instructor_password_tokens_token_hash", table_name="instructor_password_tokens")
    op.drop_index("ix_instructor_password_tokens_user_id", table_name="instructor_password_tokens")
    op.drop_table("instructor_password_tokens")
    op.drop_index("ix_instructor_profiles_instructor_id", table_name="instructor_profiles")
    op.drop_index("ix_instructor_profiles_user_id", table_name="instructor_profiles")
    op.drop_table("instructor_profiles")
