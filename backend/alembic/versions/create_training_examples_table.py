"""create training_examples table"""

from alembic import op
import sqlalchemy as sa


revision = "create_training_examples_table"
down_revision = "add_leg_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_examples",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

        sa.Column(
            "bet_leg_id",
            sa.Integer(),
            sa.ForeignKey(
                "bet_legs.id",
                ondelete="CASCADE",
            ),
            nullable=False,
            unique=True,
        ),

        sa.Column(
            "fixture_id",
            sa.Integer(),
            sa.ForeignKey(
                "fixtures.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "sport_name",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "tournament_name",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "fixture_name",
            sa.String(length=512),
            nullable=False,
        ),

        sa.Column(
            "market_name",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "outcome_name",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "odds",
            sa.Float(),
            nullable=False,
        ),

        sa.Column(
            "implied_probability",
            sa.Float(),
            nullable=False,
        ),

        sa.Column(
            "target",
            sa.Integer(),
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
        "ix_training_examples_bet_leg_id",
        "training_examples",
        ["bet_leg_id"],
    )

    op.create_index(
        "ix_training_examples_fixture_id",
        "training_examples",
        ["fixture_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_training_examples_fixture_id",
        table_name="training_examples",
    )

    op.drop_index(
        "ix_training_examples_bet_leg_id",
        table_name="training_examples",
    )

    op.drop_table(
        "training_examples"
    )