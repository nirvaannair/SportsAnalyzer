"""expand api football team statistics

Revision ID: 228479baa16c
Revises: 9cca0a7cd922
Create Date: 2026-06-07 18:57:37.809928
"""

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "228479baa16c"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "9cca0a7cd922"

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

    op.add_column(
        "api_football_team_statistics",
        sa.Column(
            "form",
            sa.String(
                length=255,
            ),
            nullable=True,
        ),
    )

    op.add_column(
        "api_football_team_statistics",
        sa.Column(
            "goal_difference",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "api_football_team_statistics",
        sa.Column(
            "clean_sheets",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "api_football_team_statistics",
        sa.Column(
            "failed_to_score",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "api_football_team_statistics",
        sa.Column(
            "home_goals_for",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "api_football_team_statistics",
        sa.Column(
            "home_goals_against",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "api_football_team_statistics",
        sa.Column(
            "away_goals_for",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "api_football_team_statistics",
        sa.Column(
            "away_goals_against",
            sa.Integer(),
            nullable=True,
        ),
    )


def downgrade() -> None:

    op.drop_column(
        "api_football_team_statistics",
        "away_goals_against",
    )

    op.drop_column(
        "api_football_team_statistics",
        "away_goals_for",
    )

    op.drop_column(
        "api_football_team_statistics",
        "home_goals_against",
    )

    op.drop_column(
        "api_football_team_statistics",
        "home_goals_for",
    )

    op.drop_column(
        "api_football_team_statistics",
        "failed_to_score",
    )

    op.drop_column(
        "api_football_team_statistics",
        "clean_sheets",
    )

    op.drop_column(
        "api_football_team_statistics",
        "goal_difference",
    )

    op.drop_column(
        "api_football_team_statistics",
        "form",
    )