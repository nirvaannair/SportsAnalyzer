"""create historical team snapshots
"""

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "3995670b5f52"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "adf4841db090"

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
        "historical_team_snapshots",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

        sa.Column(
            "fixture_id",
            sa.Integer(),
            sa.ForeignKey(
                "api_football_fixtures.id",
                ondelete="CASCADE",
            ),
            nullable=False,
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
            "snapshot_date",
            sa.DateTime(
                timezone=True,
            ),
            nullable=False,
        ),

        sa.Column(
            "played",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "wins",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "draws",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "losses",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "goals_for",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "goals_against",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "goal_difference",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "form",
            sa.Text(),
            nullable=True,
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
        "ix_historical_team_snapshots_fixture_id",
        "historical_team_snapshots",
        ["fixture_id"],
    )

    op.create_index(
        "ix_historical_team_snapshots_team_id",
        "historical_team_snapshots",
        ["team_id"],
    )

    op.create_index(
        "ix_historical_team_snapshots_fixture_team",
        "historical_team_snapshots",
        ["fixture_id", "team_id"],
        unique=True,
    )


def downgrade() -> None:

    op.drop_index(
        "ix_historical_team_snapshots_fixture_team",
        table_name="historical_team_snapshots",
    )

    op.drop_index(
        "ix_historical_team_snapshots_team_id",
        table_name="historical_team_snapshots",
    )

    op.drop_index(
        "ix_historical_team_snapshots_fixture_id",
        table_name="historical_team_snapshots",
    )

    op.drop_table(
        "historical_team_snapshots",
    )