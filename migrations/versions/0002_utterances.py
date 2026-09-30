"""utterances: transcript sentences inside each merged turn

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-30 13:55:17.958705
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'utterances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('segment_id', sa.Integer(), nullable=False),
        sa.Column('start', sa.Float(), nullable=False),
        sa.Column('end', sa.Float(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['segment_id'], ['segments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_utterances_segment_id'), 'utterances', ['segment_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_utterances_segment_id'), table_name='utterances')
    op.drop_table('utterances')
