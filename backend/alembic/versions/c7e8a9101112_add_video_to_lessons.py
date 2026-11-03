"""add video_url and video_storage_key to lessons

Revision ID: c7e8a9101112
Revises: 546cca4efff5
Create Date: 2026-11-02 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e8a9101112'
down_revision: Union[str, None] = '546cca4efff5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safely add columns if not already added by direct migration
    with op.batch_alter_table('lessons', schema=None) as batch_op:
        try:
            batch_op.add_column(sa.Column('video_url', sa.String(length=500), nullable=True))
        except Exception:
            pass
        try:
            batch_op.add_column(sa.Column('video_storage_key', sa.String(length=255), nullable=True))
        except Exception:
            pass


def downgrade() -> None:
    with op.batch_alter_table('lessons', schema=None) as batch_op:
        batch_op.drop_column('video_storage_key')
        batch_op.drop_column('video_url')
