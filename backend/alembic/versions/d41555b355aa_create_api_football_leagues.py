"""create api football leagues

Revision ID: d41555b355aa
Revises: 3d88da96fdae
Create Date: 2026-06-08 13:12:37.037065

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d41555b355aa"
down_revision: Union[str, Sequence[str], None] = "3d88da96fdae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table(
        "api_football_leagues",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

        sa.Column(
            "api_football_league_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "country",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "league_type",
            sa.String(length=100),
            nullable=True,
        ),

        sa.Column(
            "current",
            sa.Boolean(),
            nullable=True,
        ),

        sa.Column(
            "logo_url",
            sa.String(length=1000),
            nullable=True,
        ),

        sa.Column(
            "raw_json",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_api_football_leagues_api_football_league_id",
        "api_football_leagues",
        ["api_football_league_id"],
        unique=True,
    )


def downgrade() -> None:

    op.drop_index(
        "ix_api_football_leagues_api_football_league_id",
        table_name="api_football_leagues",
    )

    op.drop_table(
        "api_football_leagues",
    )