"""add team features to training_examples"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "create_training_examples_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "training_examples",
        sa.Column(
            "home_team",
            sa.String(length=255),
            nullable=True,
        ),
    )
    
    op.add_column(
        "training_examples",
        sa.Column(
            "market_type",
            sa.String(length=100),
            nullable=True,
        ),
    )
    
    op.add_column(
        "training_examples",
        sa.Column(
            "away_team",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "training_examples",
        sa.Column(
            "is_home_selection",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "training_examples",
        sa.Column(
            "is_away_selection",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "training_examples",
        "is_away_selection",
    )

    op.drop_column(
        "training_examples",
        "is_home_selection",
    )

    op.drop_column(
        "training_examples",
        "market_type",
    )

    op.drop_column(
        "training_examples",
        "away_team",
    )

    op.drop_column(
        "training_examples",
        "home_team",
    )