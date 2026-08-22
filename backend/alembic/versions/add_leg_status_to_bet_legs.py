"""add leg_status to bet_legs

Revision ID: add_leg_status
Revises: 96075e0f1804
Create Date: 2026-06-01

"""

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_leg_status"

down_revision = "create_bet_legs_table"

branch_labels = None

depends_on = None


def upgrade() -> None:
    op.add_column(
        "bet_legs",
        sa.Column(
            "leg_status",
            sa.String(length=100),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "bet_legs",
        "leg_status",
    )