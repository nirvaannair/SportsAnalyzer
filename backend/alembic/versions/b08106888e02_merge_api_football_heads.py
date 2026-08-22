"""merge api football heads

Revision ID: b08106888e02
Revises: d41555b355aa, 085f856ccf97
Create Date: 2026-06-11 13:48:44.000986

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa




revision: str = 'b08106888e02'
down_revision: Union[str, Sequence[str], None] = ('d41555b355aa', '228479baa16c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass