"""create teams and api football tables

Revision ID: 37ffc3cbe0c1
Revises: a1b2c3d4e5f6
Create Date: 2026-06-07 18:32:15.073389
"""

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "37ffc3cbe0c1"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "a1b2c3d4e5f6"

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
        "teams",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

        sa.Column(
            "sport_id",
            sa.Integer(),
            sa.ForeignKey(
                "sports.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "normalized_name",
            sa.String(length=255),
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
        "ix_teams_normalized_name",
        "teams",
        ["normalized_name"],
        unique=True,
    )

    op.create_table(
        "team_mappings",

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
            "provider",
            sa.String(length=100),
            nullable=False,
        ),

        sa.Column(
            "provider_team_id",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "provider_name",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(
                timezone=True,
            ),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_team_mappings_provider",
        "team_mappings",
        ["provider"],
    )

    op.create_index(
        "ix_team_mappings_provider_team_id",
        "team_mappings",
        ["provider_team_id"],
    )

    op.create_table(
        "api_football_teams",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

        sa.Column(
            "api_football_team_id",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "code",
            sa.String(length=50),
            nullable=True,
        ),

        sa.Column(
            "country",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "logo_url",
            sa.String(length=1024),
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
        "ix_api_football_team_id",
        "api_football_teams",
        ["api_football_team_id"],
        unique=True,
    )


def downgrade() -> None:

    op.drop_index(
        "ix_api_football_team_id",
        table_name="api_football_teams",
    )

    op.drop_table(
        "api_football_teams",
    )

    op.drop_index(
        "ix_team_mappings_provider_team_id",
        table_name="team_mappings",
    )

    op.drop_index(
        "ix_team_mappings_provider",
        table_name="team_mappings",
    )

    op.drop_table(
        "team_mappings",
    )

    op.drop_index(
        "ix_teams_normalized_name",
        table_name="teams",
    )

    op.drop_table(
        "teams",
    )