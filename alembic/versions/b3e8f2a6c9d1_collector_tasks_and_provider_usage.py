"""collector tasks and provider usage

Revision ID: b3e8f2a6c9d1
Revises: a9d4e1c7b2f0
Create Date: 2026-11-26 12:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b3e8f2a6c9d1'
down_revision: Union[str, Sequence[str], None] = 'a9d4e1c7b2f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'collector_tasks',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('provider', sa.String(length=40), nullable=False),
        sa.Column('kind', sa.String(length=40), nullable=False),
        sa.Column('endpoint', sa.String(length=300), nullable=False),
        sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('attempts', sa.SmallInteger(), server_default='0', nullable=False),
        sa.Column('items', sa.Integer(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('done_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'endpoint', 'params', name='uq_collector_tasks_request'),
    )
    op.create_index('ix_collector_tasks_queue', 'collector_tasks', ['provider', 'status', 'priority', 'id'])
    op.create_table(
        'provider_usage',
        sa.Column('provider', sa.String(length=40), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('requests', sa.Integer(), server_default='0', nullable=False),
        sa.Column('errors', sa.Integer(), server_default='0', nullable=False),
        sa.Column('remaining_reported', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('provider', 'day'),
    )


def downgrade() -> None:
    op.drop_table('provider_usage')
    op.drop_index('ix_collector_tasks_queue', table_name='collector_tasks')
    op.drop_table('collector_tasks')
