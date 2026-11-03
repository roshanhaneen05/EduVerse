"""add_video_to_lessons

Revision ID: a1c4901c0d13
Revises: 546cca4efff5
Create Date: 2026-11-02 15:25:15.375104

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c4901c0d13'
down_revision: Union[str, Sequence[str], None] = '546cca4efff5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
