"""training runs for the ML models

Revision ID: a9d4e1c7b2f0
Revises: 5f3b355be72e
Create Date: 2026-11-26 10:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a9d4e1c7b2f0'
down_revision: Union[str, Sequence[str], None] = '5f3b355be72e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'training_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('models', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('args', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('device', sa.String(length=80), nullable=True),
        sa.Column('pid', sa.Integer(), nullable=True),
        sa.Column('progress', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('results', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('training_runs')
