"""Alembic environment configuration.

Reads DATABASE_URL from environment. Uses raw SQL migrations (no ORM metadata).
"""

import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required for migrations")

# SQLAlchemy needs the psycopg (v3) driver specified explicitly.
# Normalise postgresql:// → postgresql+psycopg:// so it doesn't look for psycopg2.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL to stdout."""
    context.configure(url=DATABASE_URL, target_metadata=None, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
