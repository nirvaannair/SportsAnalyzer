"""change api football team id to integer

Revision ID: 085f856ccf97
Revises: cf9da8821193
Create Date: 2026-06-07 18:44:04.340703
"""

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "085f856ccf97"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "cf9da8821193"

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

    op.alter_column(
        "api_football_teams",
        "api_football_team_id",
        existing_type=sa.String(
            length=255,
        ),
        type_=sa.Integer(),
        postgresql_using=(
            "api_football_team_id::integer"
        ),
    )


def downgrade() -> None:

    op.alter_column(
        "api_football_teams",
        "api_football_team_id",
        existing_type=sa.Integer(),
        type_=sa.String(
            length=255,
        ),
        postgresql_using=(
            "api_football_team_id::varchar"
        ),
    )