"""create football fixture features table
"""

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "adf4841db090"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "b08106888e02"

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
        "football_fixture_features",

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
            unique=True,
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
            "home_played",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "away_played",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "home_wins",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "away_wins",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "home_draws",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "away_draws",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "home_losses",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "away_losses",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "home_goals_for",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "away_goals_for",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "home_goals_against",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "away_goals_against",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "home_goal_difference",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "away_goal_difference",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "home_clean_sheets",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "away_clean_sheets",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "home_failed_to_score",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "away_failed_to_score",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "home_form",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "away_form",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "home_xg",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "away_xg",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "home_xga",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "away_xga",
            sa.Float(),
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
        "ix_football_fixture_features_fixture_id",
        "football_fixture_features",
        ["fixture_id"],
    )

    op.create_index(
        "ix_football_fixture_features_home_team_id",
        "football_fixture_features",
        ["home_team_id"],
    )

    op.create_index(
        "ix_football_fixture_features_away_team_id",
        "football_fixture_features",
        ["away_team_id"],
    )

    op.create_index(
        "ix_football_fixture_features_league_id",
        "football_fixture_features",
        ["league_id"],
    )

    op.create_index(
        "ix_football_fixture_features_season",
        "football_fixture_features",
        ["season"],
    )


def downgrade() -> None:

    op.drop_index(
        "ix_football_fixture_features_season",
        table_name="football_fixture_features",
    )

    op.drop_index(
        "ix_football_fixture_features_league_id",
        table_name="football_fixture_features",
    )

    op.drop_index(
        "ix_football_fixture_features_away_team_id",
        table_name="football_fixture_features",
    )

    op.drop_index(
        "ix_football_fixture_features_home_team_id",
        table_name="football_fixture_features",
    )

    op.drop_index(
        "ix_football_fixture_features_fixture_id",
        table_name="football_fixture_features",
    )

    op.drop_table(
        "football_fixture_features",
    )