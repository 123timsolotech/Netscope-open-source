"""SQLite engine and session factory.

Every connection gets the pragmas required by the brief (section 4):
WAL journal mode, ``busy_timeout = 5000`` and foreign keys on.
"""

from collections.abc import Iterator
from pathlib import Path
from sqlite3 import Connection as SQLiteConnection
from typing import Any

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

BUSY_TIMEOUT_MS = 5000


def create_db_engine(database_file: Path, *, foreign_keys: bool = True) -> Engine:
    """Create an engine for a SQLite file.

    ``foreign_keys=False`` is only for migrations: Alembic's batch mode recreates tables,
    and with foreign keys on, dropping the old table would fire ON DELETE CASCADE.
    """
    engine = create_engine(
        f"sqlite:///{database_file.as_posix()}",
        # Sessions are used from FastAPI's threadpool and (M6) from the monitor's worker
        # thread. SQLAlchemy's pool hands each connection to one thread at a time.
        connect_args={"check_same_thread": False},
        # Errors never log or show statement parameters: they include the admin's password
        # hash and session ids (security audit, M2).
        hide_parameters=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection: SQLiteConnection, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS:d}")
            cursor.execute(f"PRAGMA foreign_keys = {'ON' if foreign_keys else 'OFF'}")
        finally:
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency: one session per request, closed afterwards."""
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with session_factory() as session:
        yield session
