"""forward predictions and mock bets

Revision ID: d2f5a8c1e3b7
Revises: c7d1e9b4a2f3
Create Date: 2026-11-26 18:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'd2f5a8c1e3b7'
down_revision: Union[str, Sequence[str], None] = 'c7d1e9b4a2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'forward_predictions',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('match_id', sa.Integer(), nullable=False),
        sa.Column('model', sa.String(length=48), nullable=False),
        sa.Column('kickoff_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('locked', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('p_home', sa.Float(), nullable=False),
        sa.Column('p_draw', sa.Float(), nullable=False),
        sa.Column('p_away', sa.Float(), nullable=False),
        sa.Column('p_over25', sa.Float(), nullable=True),
        sa.Column('p_btts', sa.Float(), nullable=True),
        sa.Column('raw', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('outcome', sa.String(length=8), nullable=True),
        sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('logloss_1x2', sa.Float(), nullable=True),
        sa.Column('correct_1x2', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('match_id', 'model', name='uq_forward_predictions_match_model'),
    )
    op.create_index('ix_forward_predictions_model_settled', 'forward_predictions', ['model', 'settled_at'])
    op.create_table(
        'mock_bets',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('prediction_id', sa.BigInteger(), nullable=False),
        sa.Column('rule', sa.String(length=24), nullable=False),
        sa.Column('market', sa.String(length=8), nullable=False),
        sa.Column('selection', sa.String(length=8), nullable=False),
        sa.Column('p_model', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('stake', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=8), nullable=False),
        sa.Column('profit', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['prediction_id'], ['forward_predictions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('prediction_id', 'rule', 'market', 'selection', name='uq_mock_bets_pick'),
    )


def downgrade() -> None:
    op.drop_table('mock_bets')
    op.drop_index('ix_forward_predictions_model_settled', table_name='forward_predictions')
    op.drop_table('forward_predictions')
