"""expand api football teams

Revision ID: cf9da8821193
Revises: 37ffc3cbe0c1
Create Date: 2026-06-07 18:40:49.633046
"""

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "cf9da8821193"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "37ffc3cbe0c1"

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
        "api_football_teams",
        sa.Column(
            "founded",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "api_football_teams",
        sa.Column(
            "national",
            sa.Boolean(),
            nullable=True,
        ),
    )

    op.add_column(
        "api_football_teams",
        sa.Column(
            "venue_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "api_football_teams",
        sa.Column(
            "venue_name",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "api_football_teams",
        sa.Column(
            "venue_city",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "api_football_teams",
        sa.Column(
            "venue_capacity",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "api_football_teams",
        sa.Column(
            "venue_surface",
            sa.String(length=100),
            nullable=True,
        ),
    )


def downgrade() -> None:

    op.drop_column(
        "api_football_teams",
        "venue_surface",
    )

    op.drop_column(
        "api_football_teams",
        "venue_capacity",
    )

    op.drop_column(
        "api_football_teams",
        "venue_city",
    )

    op.drop_column(
        "api_football_teams",
        "venue_name",
    )

    op.drop_column(
        "api_football_teams",
        "venue_id",
    )

    op.drop_column(
        "api_football_teams",
        "national",
    )

    op.drop_column(
        "api_football_teams",
        "founded",
    )