"""create api football team statistics

Revision ID: 9cca0a7cd922
Revises: 085f856ccf97
Create Date: 2026-06-07 18:53:45.683959
"""

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "9cca0a7cd922"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "085f856ccf97"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:

    op.create_table(
        "api_football_team_statistics",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey(
                "teams.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "api_football_team_id",
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
            "played",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "wins",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "draws",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "losses",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "goals_for",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "goals_against",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "home_played",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "home_wins",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "home_draws",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "home_losses",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "away_played",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "away_wins",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "away_draws",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "away_losses",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "raw_json",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(
                timezone=True,
            ),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(
                timezone=True,
            ),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_api_football_team_statistics_team_id",
        "api_football_team_statistics",
        ["team_id"],
    )

    op.create_index(
        "ix_api_football_team_statistics_team_league_season",
        "api_football_team_statistics",
        [
            "api_football_team_id",
            "league_id",
            "season",
        ],
        unique=True,
    )


def downgrade() -> None:

    op.drop_index(
        "ix_api_football_team_statistics_team_league_season",
        table_name="api_football_team_statistics",
    )

    op.drop_index(
        "ix_api_football_team_statistics_team_id",
        table_name="api_football_team_statistics",
    )

    op.drop_table(
        "api_football_team_statistics",
    )