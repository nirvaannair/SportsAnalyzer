"""create api football fixtures

Revision ID: 3d88da96fdae
Revises: 228479baa16c
Create Date: 2026-06-08 12:45:43.990281

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3d88da96fdae"
down_revision: Union[str, Sequence[str], None] = "cf9da8821193"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table(
        "api_football_fixtures",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

        sa.Column(
            "api_football_fixture_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "league_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "season",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "home_team_id",
            sa.Integer(),
            sa.ForeignKey(
                "teams.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "away_team_id",
            sa.Integer(),
            sa.ForeignKey(
                "teams.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "home_goals",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "away_goals",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "winner_team_id",
            sa.Integer(),
            sa.ForeignKey(
                "teams.id",
                ondelete="CASCADE",
            ),
            nullable=True,
        ),

        sa.Column(
            "status",
            sa.String(length=50),
            nullable=True,
        ),

        sa.Column(
            "fixture_date",
            sa.DateTime(timezone=True),
            nullable=False,
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
        "ix_api_football_fixtures_api_football_fixture_id",
        "api_football_fixtures",
        ["api_football_fixture_id"],
        unique=True,
    )

    op.create_index(
        "ix_api_football_fixtures_league_id",
        "api_football_fixtures",
        ["league_id"],
    )

    op.create_index(
        "ix_api_football_fixtures_season",
        "api_football_fixtures",
        ["season"],
    )

    op.create_index(
        "ix_api_football_fixtures_home_team_id",
        "api_football_fixtures",
        ["home_team_id"],
    )

    op.create_index(
        "ix_api_football_fixtures_away_team_id",
        "api_football_fixtures",
        ["away_team_id"],
    )


def downgrade() -> None:

    op.drop_index(
        "ix_api_football_fixtures_away_team_id",
        table_name="api_football_fixtures",
    )

    op.drop_index(
        "ix_api_football_fixtures_home_team_id",
        table_name="api_football_fixtures",
    )

    op.drop_index(
        "ix_api_football_fixtures_season",
        table_name="api_football_fixtures",
    )

    op.drop_index(
        "ix_api_football_fixtures_league_id",
        table_name="api_football_fixtures",
    )

    op.drop_index(
        "ix_api_football_fixtures_api_football_fixture_id",
        table_name="api_football_fixtures",
    )

    op.drop_table(
        "api_football_fixtures",
    )