"""Apply database migrations at startup, with a backup first.

Before any pending migration is applied to an existing database, the database is copied to
``<name>.bak-<UTC timestamp>`` next to it. Only the newest ``BACKUPS_TO_KEEP`` backups are kept.

The copy uses SQLite's online backup API, so it is consistent even in WAL mode (copying the
file alone could miss data still in the ``-wal`` file).
"""

import logging
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.core.db import create_db_engine
from app.core.timeutil import utcnow

logger = logging.getLogger("netscope.migrate")

BACKUPS_TO_KEEP = 3
BACKUP_MARKER = ".bak-"
# Sortable as text, microseconds so two backups in the same second never collide.
BACKUP_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%S.%fZ"
# What BACKUP_TIMESTAMP_FORMAT writes: a backup's name is the database's, the marker and this,
# nothing more. Other files next to it (a backup's own -wal file, "...Z.old", a copy the user
# named) are never listed, so never pruned (found in the M8 review).
BACKUP_TIMESTAMP_PATTERN = r"\d{8}T\d{6}\.\d{6}Z"
# Files SQLite may keep next to a database (or a backup someone opened).
SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")

# New database folders, databases and backups are private to the user running NetScope:
# they hold the admin's password hash (security audit, M2). SQLite gives the -wal/-shm files
# the database file's mode. Existing files keep whatever mode they have.
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600

WAL_FILES = ("-wal", "-shm")

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
MIGRATIONS_DIR = BACKEND_DIR / "migrations"


def alembic_config(database_file: Path) -> Config:
    """Alembic config that works from any working directory."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.attributes["database_file"] = database_file
    config.attributes["skip_logging_config"] = True
    return config


def head_revision(config: Config) -> str | None:
    return ScriptDirectory.from_config(config).get_current_head()


def current_revision(database_file: Path) -> str | None:
    """Revision the database is at, or None for a new/empty database."""
    engine = create_db_engine(database_file)
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


def has_data(database_file: Path) -> bool:
    """True if the file exists and holds at least one table."""
    if not database_file.is_file() or database_file.stat().st_size == 0:
        return False
    with closing(sqlite3.connect(database_file)) as connection:
        row = connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type = 'table'"
        ).fetchone()
    return bool(row and row[0] > 0)


def database_open_to_others(database_file: Path) -> bool:
    """True if any user of the computer may read or write the database (POSIX "other" bits).

    Only reported, never changed: group access may be on purpose (a backup tool).
    """
    if os.name == "nt" or not database_file.is_file():
        return False
    return bool(database_file.stat().st_mode & 0o006)


def backup_database(
    database_file: Path, *, now: datetime | None = None, marker: str = BACKUP_MARKER
) -> Path:
    """Copy the database to ``<name><marker><timestamp>`` (``<name>.bak-<timestamp>`` before
    migrations) and return the backup path. The import (M8) uses its own marker, so its
    copies and the migration backups are kept and pruned separately."""
    stamp = (now or utcnow()).strftime(BACKUP_TIMESTAMP_FORMAT)
    backup_file = database_file.with_name(f"{database_file.name}{marker}{stamp}")
    backup_file.touch(mode=PRIVATE_FILE_MODE, exist_ok=False)
    with (
        closing(sqlite3.connect(database_file)) as source,
        closing(sqlite3.connect(backup_file)) as target,
    ):
        source.backup(target)
    return backup_file


def list_backups(database_file: Path, marker: str = BACKUP_MARKER) -> list[Path]:
    """Backups of this database with this marker, oldest first: only files named exactly
    ``<name><marker><timestamp>``."""
    exact = re.compile(re.escape(f"{database_file.name}{marker}") + BACKUP_TIMESTAMP_PATTERN)
    folder = database_file.parent
    if not folder.is_dir():
        return []
    backups = [path for path in folder.iterdir() if exact.fullmatch(path.name) and path.is_file()]
    return sorted(backups, key=lambda path: path.name)


def prune_backups(
    database_file: Path, keep: int = BACKUPS_TO_KEEP, marker: str = BACKUP_MARKER
) -> list[Path]:
    """Delete all but the newest ``keep`` backups with this marker. Returns the deleted
    paths."""
    backups = list_backups(database_file, marker)
    stale = backups[:-keep] if keep > 0 else backups
    for path in stale:
        path.unlink()
        for suffix in SIDECAR_SUFFIXES:  # left over if the copy was ever opened
            path.with_name(f"{path.name}{suffix}").unlink(missing_ok=True)
    return stale


def require_writable(database_file: Path) -> None:
    """Stop with a clear message when NetScope cannot write its folder or database.

    Otherwise a database copied in with another owner started "healthy" and every write
    failed ("attempt to write a readonly database"), and an unwritable folder crashed with a
    bare traceback (found in the M8 review). SQLite also needs the folder for its -wal and
    -shm files.
    """
    folder = database_file.parent
    blocked = []
    if folder.exists() and not os.access(folder, os.W_OK | os.X_OK):
        blocked.append(f"the folder {folder}")
    for path in (database_file, *(folder / f"{database_file.name}{end}" for end in WAL_FILES)):
        if path.exists() and not os.access(path, os.R_OK | os.W_OK):
            blocked.append(str(path))
    if blocked:
        raise RuntimeError(cannot_write(blocked))


def cannot_write(blocked: list[str]) -> str:
    user = f"user id {os.getuid()}" if hasattr(os, "getuid") else "this user"
    return (
        f"NetScope (running as {user}) cannot write {', '.join(blocked)}. Give that user the "
        "folder and the database files (in Docker: the chown in docs/deployment.md, section 5, "
        '"Restore a full copy").'
    )


def migrate_database(database_file: Path) -> Path | None:
    """Bring the database to the latest revision.

    Returns the backup path if a backup was made (pending migrations on an existing
    database), else None. Raises if a migration fails; the backup is kept.
    """
    try:
        database_file.parent.mkdir(mode=PRIVATE_DIR_MODE, parents=True, exist_ok=True)
    except PermissionError:
        raise RuntimeError(cannot_write([f"the folder {database_file.parent}"])) from None
    require_writable(database_file)
    # Created empty first, so SQLite opens a file that is already private (an empty file
    # counts as a new database below).
    if not database_file.exists():
        database_file.touch(mode=PRIVATE_FILE_MODE)
    config = alembic_config(database_file)
    head = head_revision(config)

    backup_file: Path | None = None
    if has_data(database_file):
        current = current_revision(database_file)
        if current == head:
            logger.info("Database is up to date (revision %s).", current)
            return None
        backup_file = backup_database(database_file)
        logger.info(
            "Pending migrations (%s -> %s). Backup written to %s",
            current or "none",
            head,
            backup_file,
        )
        for path in prune_backups(database_file):
            logger.info("Removed old backup %s", path)
    else:
        logger.info("Creating new database at %s", database_file)

    try:
        command.upgrade(config, "head")
    except Exception:
        if backup_file is not None:
            logger.exception(
                "Migration failed. The database before migrating is saved at %s. "
                "To restore: stop NetScope, delete %s and its -wal/-shm files, "
                "then copy the backup to %s.",
                backup_file,
                database_file,
                database_file,
            )
        raise
    logger.info("Database migrated to revision %s.", head)
    return backup_file
