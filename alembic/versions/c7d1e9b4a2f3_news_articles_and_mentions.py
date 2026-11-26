"""news articles and mentions

Revision ID: c7d1e9b4a2f3
Revises: b3e8f2a6c9d1
Create Date: 2026-11-26 15:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'c7d1e9b4a2f3'
down_revision: Union[str, Sequence[str], None] = 'b3e8f2a6c9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'news_articles',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('provider', sa.String(length=40), nullable=False),
        sa.Column('external_id', sa.String(length=80), nullable=False),
        sa.Column('league', sa.String(length=8), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('headline', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('topics', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('sentiment', sa.Float(), nullable=False),
        sa.Column('injury', sa.Boolean(), nullable=False),
        sa.Column('signals', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'external_id', name='uq_news_articles_provider_id'),
    )
    op.create_index('ix_news_articles_published', 'news_articles', ['published_at'])
    op.create_table(
        'news_mentions',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('article_id', sa.BigInteger(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=True),
        sa.Column('player_id', sa.Integer(), nullable=True),
        sa.Column('provider_team_id', sa.String(length=40), nullable=True),
        sa.Column('label', sa.String(length=160), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['article_id'], ['news_articles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id']),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_news_mentions_team', 'news_mentions', ['team_id', 'article_id'])


def downgrade() -> None:
    op.drop_index('ix_news_mentions_team', table_name='news_mentions')
    op.drop_table('news_mentions')
    op.drop_index('ix_news_articles_published', table_name='news_articles')
    op.drop_table('news_articles')
