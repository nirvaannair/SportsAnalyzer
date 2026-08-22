"""create bet legs table"""

from alembic import op
import sqlalchemy as sa


revision = "create_bet_legs_table"
down_revision = "96075e0f1804"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bet_legs",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

        sa.Column(
            "stake_bet_id",
            sa.String(255),
            nullable=False,
        ),

        sa.Column(
            "stake_bet_slip_id",
            sa.String(255),
            nullable=True,
        ),

        sa.Column(
            "bet_history_id",
            sa.Integer(),
            sa.ForeignKey(
                "bet_history.id",
                ondelete="CASCADE",
            ),
            nullable=True,
        ),

        sa.Column(
            "fixture_id",
            sa.String(255),
            nullable=True,
        ),

        sa.Column(
            "fixture_name",
            sa.String(512),
            nullable=True,
        ),

        sa.Column(
            "fixture_slug",
            sa.String(512),
            nullable=True,
        ),

        sa.Column(
            "market_id",
            sa.String(255),
            nullable=True,
        ),

        sa.Column(
            "market_name",
            sa.String(255),
            nullable=True,
        ),

        sa.Column(
            "outcome_id",
            sa.String(255),
            nullable=True,
        ),

        sa.Column(
            "outcome_name",
            sa.String(255),
            nullable=True,
        ),

        sa.Column(
            "odds",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "total_odds",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "market_status",
            sa.String(100),
            nullable=True,
        ),

        sa.Column(
            "fixture_status",
            sa.String(100),
            nullable=True,
        ),

        sa.Column(
            "bet_status",
            sa.String(100),
            nullable=True,
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
        "ix_bet_legs_stake_bet_id",
        "bet_legs",
        ["stake_bet_id"],
    )

    op.create_index(
        "ix_bet_legs_stake_bet_slip_id",
        "bet_legs",
        ["stake_bet_slip_id"],
    )

    op.create_index(
        "ix_bet_legs_fixture_id",
        "bet_legs",
        ["fixture_id"],
    )

    op.create_index(
        "ix_bet_legs_market_id",
        "bet_legs",
        ["market_id"],
    )

    op.create_index(
        "ix_bet_legs_outcome_id",
        "bet_legs",
        ["outcome_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bet_legs_outcome_id",
        table_name="bet_legs",
    )

    op.drop_index(
        "ix_bet_legs_market_id",
        table_name="bet_legs",
    )

    op.drop_index(
        "ix_bet_legs_fixture_id",
        table_name="bet_legs",
    )

    op.drop_index(
        "ix_bet_legs_stake_bet_slip_id",
        table_name="bet_legs",
    )

    op.drop_index(
        "ix_bet_legs_stake_bet_id",
        table_name="bet_legs",
    )

    op.drop_table(
        "bet_legs"
    )