"""initial_eduverse_schema

Revision ID: fb4ef543d5d3
Revises: 4c74afdb0575
Create Date: 2026-11-01 13:34:03.899051

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fb4ef543d5d3'
down_revision: Union[str, Sequence[str], None] = '4c74afdb0575'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema safely preserving existing data."""
    # 1. Create ai_messages table
    op.create_table(
        'ai_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['ai_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('ai_messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ai_messages_conversation_id'), ['conversation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_ai_messages_id'), ['id'], unique=False)

    # 2. Update ai_conversations
    with op.batch_alter_table('ai_conversations', schema=None) as batch_op:
        try:
            batch_op.drop_index(batch_op.f('ix_ai_conversations_course_id'))
        except Exception:
            pass
        batch_op.drop_column('course_id')
        batch_op.drop_column('messages_json')

    # 3. Update answer_options
    with op.batch_alter_table('answer_options', schema=None) as batch_op:
        batch_op.drop_column('order_index')

    # 4. Update users: populate password_hash from hashed_password
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('password_hash', sa.String(length=255), server_default='', nullable=False))
    
    op.execute("UPDATE users SET password_hash = hashed_password WHERE password_hash = '' OR password_hash IS NULL")

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('hashed_password')
        batch_op.drop_column('avatar_url')
        batch_op.drop_column('bio')

    # 5. Update courses: add difficulty
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('difficulty', sa.String(length=50), server_default='Beginner', nullable=False))
        try:
            batch_op.drop_index(batch_op.f('ix_courses_slug'))
        except Exception:
            pass
        batch_op.drop_column('short_description')
        batch_op.drop_column('thumbnail_url')
        batch_op.drop_column('level')
        batch_op.drop_column('slug')

    # 6. Update course_enrollments: student_id and completion_percentage
    with op.batch_alter_table('course_enrollments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('student_id', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('completion_percentage', sa.Float(), server_default='0.0', nullable=False))

    op.execute("UPDATE course_enrollments SET student_id = user_id WHERE student_id = 0")
    op.execute("UPDATE course_enrollments SET completion_percentage = progress_percentage WHERE completion_percentage = 0.0")

    with op.batch_alter_table('course_enrollments', schema=None) as batch_op:
        try:
            batch_op.drop_index(batch_op.f('ix_course_enrollments_user_id'))
            batch_op.drop_constraint('uq_user_course_enrollment', type_='unique')
        except Exception:
            pass
        batch_op.create_index(batch_op.f('ix_course_enrollments_student_id'), ['student_id'], unique=False)
        batch_op.create_unique_constraint('uq_student_course_enrollment', ['student_id', 'course_id'])
        batch_op.create_foreign_key('fk_course_enrollments_student_id', 'users', ['student_id'], ['id'], ondelete='CASCADE')
        batch_op.drop_column('progress_percentage')
        batch_op.drop_column('completed_at')
        batch_op.drop_column('user_id')

    # 7. Update lessons
    with op.batch_alter_table('lessons', schema=None) as batch_op:
        batch_op.drop_column('duration_minutes')
        batch_op.drop_column('video_url')

    # 8. Update lesson_progress: student_id and updated_at
    with op.batch_alter_table('lesson_progress', schema=None) as batch_op:
        batch_op.add_column(sa.Column('student_id', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    op.execute("UPDATE lesson_progress SET student_id = user_id WHERE student_id = 0")

    with op.batch_alter_table('lesson_progress', schema=None) as batch_op:
        try:
            batch_op.drop_index(batch_op.f('ix_lesson_progress_user_id'))
            batch_op.drop_constraint('uq_user_lesson_progress', type_='unique')
        except Exception:
            pass
        batch_op.create_index(batch_op.f('ix_lesson_progress_student_id'), ['student_id'], unique=False)
        batch_op.create_unique_constraint('uq_student_lesson_progress', ['student_id', 'lesson_id'])
        batch_op.create_foreign_key('fk_lesson_progress_student_id', 'users', ['student_id'], ['id'], ondelete='CASCADE')
        batch_op.drop_column('user_id')

    # 9. Update questions: add points
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('points', sa.Integer(), server_default='1', nullable=False))
        batch_op.drop_column('explanation')

    # 10. Update quiz_attempts & quiz_attempt_answers
    with op.batch_alter_table('quiz_attempt_answers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('awarded_points', sa.Integer(), server_default='0', nullable=False))
        batch_op.create_index(batch_op.f('ix_quiz_attempt_answers_question_id'), ['question_id'], unique=False)
        batch_op.create_unique_constraint('uq_attempt_question', ['attempt_id', 'question_id'])

    with op.batch_alter_table('quiz_attempts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('student_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('total_points', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
        batch_op.alter_column('quiz_id', existing_type=sa.INTEGER(), nullable=True)

    op.execute("UPDATE quiz_attempts SET student_id = user_id WHERE student_id IS NULL")

    with op.batch_alter_table('quiz_attempts', schema=None) as batch_op:
        try:
            batch_op.drop_index(batch_op.f('ix_quiz_attempts_user_id'))
        except Exception:
            pass
        batch_op.create_index(batch_op.f('ix_quiz_attempts_student_id'), ['student_id'], unique=False)
        batch_op.create_foreign_key('fk_quiz_attempts_student_id', 'users', ['student_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_quiz_attempts_quiz_id', 'quizzes', ['quiz_id'], ['id'], ondelete='SET NULL')
        batch_op.drop_column('total_questions')
        batch_op.drop_column('points_scored')
        batch_op.drop_column('user_id')

    # 11. Update quizzes: remove time_limit_minutes
    with op.batch_alter_table('quizzes', schema=None) as batch_op:
        batch_op.drop_column('time_limit_minutes')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('ai_messages')
