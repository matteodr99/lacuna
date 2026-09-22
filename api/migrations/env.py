"""Alembic environment.

The database URL is NOT configured in alembic.ini. It comes from
db_schema, which reads DATABASE_URL (SQLite locally, Neon Postgres in
production) and rewrites Neon's `postgresql://` scheme for psycopg 3.
Keeping one source of truth means `alembic upgrade head` can never run
against a different database than the application.

`render_as_batch` is on for SQLite: SQLite cannot ALTER most things, so
Alembic emulates it by creating a new table, copying the rows and
swapping the names. Without it, the first migration that alters a column
would fail locally while working fine on Postgres — the worst possible
place to discover the difference.
"""

from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

# Importing db_schema registers every model on SQLModel.metadata, which is
# what --autogenerate compares against the live database. A model not
# imported here is a model Alembic will propose to DROP.
import db_schema  # noqa: F401
from db_schema import DATABASE_URL, engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it, for review or for a DBA."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_is_sqlite(DATABASE_URL),
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the application's own engine."""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_is_sqlite(DATABASE_URL),
            # Without this, a changed column type is silently ignored by
            # autogenerate — a migration that looks complete and isn't.
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
