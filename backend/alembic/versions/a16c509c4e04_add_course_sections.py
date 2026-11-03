"""add_course_sections

Revision ID: a16c509c4e04
Revises: fb4ef543d5d3
Create Date: 2026-11-01 15:17:20.195560

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a16c509c4e04'
down_revision: Union[str, Sequence[str], None] = 'fb4ef543d5d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'course_sections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('order_index >= 1', name='ck_section_order_index_positive'),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('course_sections', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_course_sections_course_id'), ['course_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_course_sections_id'), ['id'], unique=False)

    with op.batch_alter_table('answer_options', schema=None) as batch_op:
        batch_op.add_column(sa.Column('order_index', sa.Integer(), nullable=False, server_default='1'))

    with op.batch_alter_table('lessons', schema=None) as batch_op:
        batch_op.add_column(sa.Column('section_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_lessons_section_id'), ['section_id'], unique=False)
        batch_op.create_foreign_key('fk_lessons_section_id', 'course_sections', ['section_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('lessons', schema=None) as batch_op:
        batch_op.drop_constraint('fk_lessons_section_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_lessons_section_id'))
        batch_op.drop_column('section_id')

    with op.batch_alter_table('answer_options', schema=None) as batch_op:
        batch_op.drop_column('order_index')

    with op.batch_alter_table('course_sections', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_course_sections_id'))
        batch_op.drop_index(batch_op.f('ix_course_sections_course_id'))

    op.drop_table('course_sections')
