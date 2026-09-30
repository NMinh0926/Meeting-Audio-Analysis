"""initial schema: meetings, speakers, segments

Revision ID: 0001
Revises:
Create Date: 2026-09-30 01:00:49.100226
"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

meeting_status = sa.Enum('queued', 'processing', 'done', 'failed', name='meeting_status')


def upgrade() -> None:
    op.create_table(
        'meetings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('seq', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('storage_key', sa.String(length=512), nullable=False),
        sa.Column('status', meeting_status, nullable=False),
        sa.Column('current_stage', sa.String(length=50), nullable=True),
        sa.Column('error_code', sa.String(length=100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('speaker_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('seq'),
        sa.UniqueConstraint('storage_key'),
    )
    op.create_index('ix_meetings_status_seq', 'meetings', ['status', 'seq'], unique=False)
    op.create_table(
        'speakers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Uuid(), nullable=False),
        sa.Column('label', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('gender', sa.String(length=20), nullable=False),
        sa.Column('gender_confidence', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_speakers_meeting_id'), 'speakers', ['meeting_id'], unique=False)
    op.create_table(
        'segments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Uuid(), nullable=False),
        sa.Column('speaker_id', sa.Integer(), nullable=False),
        sa.Column('start', sa.Float(), nullable=False),
        sa.Column('end', sa.Float(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('sentiment', sa.String(length=20), nullable=False),
        sa.Column('sentiment_confidence', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['speaker_id'], ['speakers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_segments_meeting_id'), 'segments', ['meeting_id'], unique=False)
    op.create_index(op.f('ix_segments_speaker_id'), 'segments', ['speaker_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_segments_speaker_id'), table_name='segments')
    op.drop_index(op.f('ix_segments_meeting_id'), table_name='segments')
    op.drop_table('segments')
    op.drop_index(op.f('ix_speakers_meeting_id'), table_name='speakers')
    op.drop_table('speakers')
    op.drop_index('ix_meetings_status_seq', table_name='meetings')
    op.drop_table('meetings')
    meeting_status.drop(op.get_bind())
