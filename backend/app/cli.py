"""Admin commands: ``netscope reset-password`` (brief section 7) and ``netscope seed``.

Works next to a running app (SQLite WAL), for example ``docker compose exec netscope netscope
reset-password``.
"""

import argparse
import getpass
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TextIO

from sqlalchemy.orm import Session as DbSession

from app.core.config import get_settings
from app.core.db import create_db_engine, create_session_factory
from app.core.logs import configure_logging
from app.core.migrate import has_data, migrate_database
from app.core.security import password_problem
from app.services import auth as auth_service
from app.services import seed as seed_service
from app.services.errors import ServiceError
from app.services.oui import load_bundled_oui
from app.services.seed_data import DEFAULT_CATEGORIES


class CliError(Exception):
    pass


def read_new_password(from_stdin: bool, stdin: TextIO | None = None) -> str:
    if from_stdin:
        line = (stdin or sys.stdin).readline()
        return line.rstrip("\r\n")
    first = getpass.getpass("New password: ")
    second = getpass.getpass("Repeat new password: ")
    if first != second:
        raise CliError("The passwords do not match.")
    return first


@contextmanager
def existing_database() -> Iterator[DbSession]:
    """A session on the configured database, migrated to the latest revision.

    Never creates a database: a missing one usually means the wrong working directory.
    """
    settings = get_settings()
    if not has_data(settings.database_file):
        raise CliError(
            f"No NetScope database at {settings.database_file}. Run this from backend/ "
            "or set NETSCOPE_DATABASE_PATH. Start NetScope once to create it."
        )
    migrate_database(settings.database_file)
    engine = create_db_engine(settings.database_file)
    try:
        with create_session_factory(engine)() as db:
            yield db
    finally:
        engine.dispose()


def reset_password(from_stdin: bool) -> str:
    with existing_database() as db:
        if auth_service.get_admin(db) is None:
            raise CliError(auth_service.NoAdminAccountError().message)
        password = read_new_password(from_stdin)
        problem = password_problem(password)
        if problem:
            raise CliError(problem)
        user = auth_service.reset_password(db, password)
        return user.username


def seed(demo: bool) -> list[str]:
    """Add missing default categories (and the demo data). Returns lines to print."""
    with existing_database() as db:
        added = seed_service.add_missing_default_categories(db)
        if added:
            lines = [f"Added {len(added)} default categories: {', '.join(added)}."]
        else:
            lines = [f"All {len(DEFAULT_CATEGORIES)} default categories already exist."]
        if demo:
            result = seed_service.add_demo_data(db, load_bundled_oui())
            lines.append(
                f"Added {len(result.devices_added)} demo devices and {result.links_added} links."
            )
            if result.devices_skipped:
                lines.append(
                    f"Skipped {len(result.devices_skipped)} demo devices whose names already "
                    f"exist: {', '.join(result.devices_skipped)}."
                )
            if result.devices_added:
                lines.append("Demo checks are configured but turned off.")
        return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="netscope", description="NetScope admin commands.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    reset = commands.add_parser(
        "reset-password",
        help="set a new admin password and log out every session",
        description="Set a new admin password and log out every session.",
    )
    reset.add_argument(
        "--password-stdin",
        action="store_true",
        help="read the new password from the first line of standard input instead of asking",
    )
    seed_parser = commands.add_parser(
        "seed",
        help="add missing default categories (and demo data with --demo)",
        description=(
            "Add the default categories that do not exist yet. Never overwrites or duplicates: "
            "names that exist in any letter case are left alone."
        ),
    )
    seed_parser.add_argument(
        "--demo",
        action="store_true",
        help="also add demo devices and links (their status checks stay turned off)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(get_settings().log_level)
    try:
        if args.command == "reset-password":
            username = reset_password(args.password_stdin)
            print(f"Password for '{username}' updated. All sessions were logged out.")
        elif args.command == "seed":
            for line in seed(args.demo):
                print(line)
    except (CliError, ServiceError) as error:
        message = error.message if isinstance(error, ServiceError) else str(error)
        print(f"Error: {message}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
