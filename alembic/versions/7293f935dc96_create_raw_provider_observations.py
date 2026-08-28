"""create raw provider observations

Revision ID: 7293f935dc96
Revises:
Create Date: 2026-08-28 14:21:27.229065

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "7293f935dc96"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "raw_provider_observations",
        sa.Column(
            "id",
            sa.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "provider_name",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "endpoint",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            "request_id",
            sa.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "provider_entity_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "provider_timestamp",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "request_parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "response_headers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "payload_format",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "payload_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "http_status",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_raw_provider_observations_payload_hash",
        "raw_provider_observations",
        ["provider_name", "payload_hash"],
        unique=False,
    )

    op.create_index(
        "ix_raw_provider_observations_provider_endpoint",
        "raw_provider_observations",
        ["provider_name", "endpoint"],
        unique=False,
    )

    op.create_index(
        "ix_raw_provider_observations_provider_entity",
        "raw_provider_observations",
        [
            "provider_name",
            "entity_type",
            "provider_entity_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_raw_provider_observations_received_at",
        "raw_provider_observations",
        ["received_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index(
        "ix_raw_provider_observations_received_at",
        table_name="raw_provider_observations",
    )

    op.drop_index(
        "ix_raw_provider_observations_provider_entity",
        table_name="raw_provider_observations",
    )

    op.drop_index(
        "ix_raw_provider_observations_provider_endpoint",
        table_name="raw_provider_observations",
    )

    op.drop_index(
        "ix_raw_provider_observations_payload_hash",
        table_name="raw_provider_observations",
    )

    op.drop_table("raw_provider_observations")