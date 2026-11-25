"""Alembic environment for NetScope (SQLite).

- The database path comes from the app settings, or from ``config.attributes["database_file"]``
  when migrations are run by the app at startup (see app/core/migrate.py).
- ``render_as_batch=True``: SQLite cannot ALTER most things, so Alembic recreates tables.
- Foreign keys are OFF while migrating. With them on, batch mode's "drop old table" step
  would fire ON DELETE CASCADE and wipe child rows. A foreign key check runs at the end.
"""

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import create_db_engine
from app.models import Base

config = context.config

# Only configure logging when run from the command line. When the app runs migrations at
# startup it has its own logging, which fileConfig would otherwise replace.
if config.config_file_name is not None and not config.attributes.get("skip_logging_config"):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_file() -> Path:
    override = config.attributes.get("database_file")
    if override is not None:
        return Path(override)
    return get_settings().database_file


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it (``alembic upgrade head --sql``)."""
    context.configure(
        url=f"sqlite:///{_database_file().as_posix()}",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    database_file = _database_file()
    database_file.parent.mkdir(parents=True, exist_ok=True)
    engine = create_db_engine(database_file, foreign_keys=False)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=True,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()

            violations = connection.execute(text("PRAGMA foreign_key_check")).fetchall()
            if violations:
                raise RuntimeError(f"Foreign key violations after migration: {violations}")
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
