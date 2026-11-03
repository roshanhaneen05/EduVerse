"""add_quiz_exam_features

Revision ID: bb93de15b91d
Revises: b215a54d351b
Create Date: 2026-11-01 16:38:18.753761

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb93de15b91d'
down_revision: Union[str, Sequence[str], None] = 'b215a54d351b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('quiz_attempts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('attempt_number', sa.Integer(), nullable=False, server_default=sa.text('1')))
        batch_op.add_column(sa.Column('is_completed', sa.Boolean(), nullable=False, server_default=sa.text('1')))

    with op.batch_alter_table('quizzes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('section_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('lesson_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.text('1')))
        batch_op.add_column(sa.Column('time_limit_minutes', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('max_attempts', sa.Integer(), nullable=False, server_default=sa.text('3')))
        batch_op.create_index(batch_op.f('ix_quizzes_lesson_id'), ['lesson_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_quizzes_section_id'), ['section_id'], unique=False)
        batch_op.create_foreign_key('fk_quizzes_lesson_id', 'lessons', ['lesson_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_quizzes_section_id', 'course_sections', ['section_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('quizzes', schema=None) as batch_op:
        batch_op.drop_constraint('fk_quizzes_lesson_id', type_='foreignkey')
        batch_op.drop_constraint('fk_quizzes_section_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_quizzes_section_id'))
        batch_op.drop_index(batch_op.f('ix_quizzes_lesson_id'))
        batch_op.drop_column('max_attempts')
        batch_op.drop_column('time_limit_minutes')
        batch_op.drop_column('is_published')
        batch_op.drop_column('lesson_id')
        batch_op.drop_column('section_id')

    with op.batch_alter_table('quiz_attempts', schema=None) as batch_op:
        batch_op.drop_column('is_completed')
        batch_op.drop_column('attempt_number')
