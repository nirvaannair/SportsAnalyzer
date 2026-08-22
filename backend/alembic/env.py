from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config
from sqlalchemy import pool

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
    .parent
)
load_dotenv(
    PROJECT_ROOT / ".env"
)
sys.path.insert(
    0,
    str(PROJECT_ROOT),
)

from backend.database.base import Base

import backend.database.models.__all_models


config = context.config

print(
    "POSTGRES_HOST =",
    os.getenv("POSTGRES_HOST")
)

print(
    "POSTGRES_PORT =",
    os.getenv("POSTGRES_PORT")
)

print(
    "POSTGRES_DB =",
    os.getenv("POSTGRES_DB")
)

print(
    "POSTGRES_USER =",
    os.getenv("POSTGRES_USER")
)

DATABASE_URL = (
    f"postgresql+psycopg2://"
    f"{os.getenv('POSTGRES_USER')}:"
    f"{os.getenv('POSTGRES_PASSWORD')}@"
    f"{os.getenv('POSTGRES_HOST')}:"
    f"{os.getenv('POSTGRES_PORT')}/"
    f"{os.getenv('POSTGRES_DB')}"
)

config.set_main_option(
    "sqlalchemy.url",
    DATABASE_URL,
)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(
            config.config_ini_section
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()