"""Settings the user changes in the app (brief section 6: the ``app_settings`` table).

Each value is stored as text under its key, and only once the user has changed it: a value
never changed follows the default, so a later version can improve a default for everyone
who kept it. Reading types every value and checks it against its range; a stored value that
is broken (edited by hand) is replaced by its default, with a warning in the log.
"""

import logging
from dataclasses import dataclass, fields, replace

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session as DbSession

from app.models import AppSetting
from app.schemas.settings import (
    CHECK_INTERVAL_SECONDS,
    CHECK_TIMEOUT_SECONDS,
    FAILURES_BEFORE_DOWN,
    RETENTION_DAYS,
    Limits,
    SettingsUpdate,
)
from app.services.errors import InvalidInputError, Issue

logger = logging.getLogger("netscope.settings")

LIMITS: dict[str, Limits] = {
    "check_interval_seconds": CHECK_INTERVAL_SECONDS,
    "check_timeout_seconds": CHECK_TIMEOUT_SECONDS,
    "failures_before_down": FAILURES_BEFORE_DOWN,
    "retention_days": RETENTION_DAYS,
}

# Broken stored values already reported, so the monitor (which reads the settings every few
# seconds) does not repeat the warning.
_reported: set[tuple[str, str]] = set()


@dataclass(frozen=True)
class AppSettings:
    check_interval_seconds: int = CHECK_INTERVAL_SECONDS.default
    check_timeout_seconds: int = CHECK_TIMEOUT_SECONDS.default
    failures_before_down: int = FAILURES_BEFORE_DOWN.default
    retention_days: int = RETENTION_DAYS.default


def get_settings(db: DbSession) -> AppSettings:
    """The settings in effect."""
    settings = _stored(db)
    longest = settings.check_interval_seconds // 2
    if settings.check_timeout_seconds > longest:
        # Only reachable by editing the database (updates check the rule).
        _report(
            "check_timeout_seconds",
            str(settings.check_timeout_seconds),
            f"more than half the interval; using {longest}",
        )
        settings = replace(settings, check_timeout_seconds=longest)
    return settings


def stored_values(db: DbSession) -> dict[str, int]:
    """The values the user changed (key -> value), as the export writes them (M8): only valid
    ones, and a timeout above half the interval capped as ``get_settings`` caps it, so an
    exported file always passes the import's checks."""
    values = _stored_values(db)
    if "check_timeout_seconds" in values:
        values["check_timeout_seconds"] = get_settings(db).check_timeout_seconds
    return values


def _stored(db: DbSession) -> AppSettings:
    """Stored values (defaults for the rest), each within its range."""
    return AppSettings(**_stored_values(db))


def _stored_values(db: DbSession) -> dict[str, int]:
    """The stored values that are valid, each within its range (broken ones are left out)."""
    stored = {key: value for key, value in db.execute(select(AppSetting.key, AppSetting.value))}
    values: dict[str, int] = {}
    for field in fields(AppSettings):
        raw = stored.get(field.name)
        if raw is None:
            continue
        value = _parse(field.name, raw)
        if value is not None:
            values[field.name] = value
    return values


def update_settings(db: DbSession, data: SettingsUpdate) -> AppSettings:
    """Partial update. The timeout must be at most half the interval.

    The new values are written first and checked afterwards, inside the same transaction:
    the write holds SQLite's write lock, so two parallel updates cannot each pass the check
    against the other's old value and together store a broken pair.
    """
    changes: dict[str, int] = data.model_dump(exclude_unset=True)
    if not changes:
        return get_settings(db)
    for key, value in changes.items():
        statement = insert(AppSetting).values(key=key, value=str(value))
        db.execute(
            statement.on_conflict_do_update(
                index_elements=[AppSetting.key], set_={"value": statement.excluded.value}
            )
        )
    settings = _stored(db)
    issue = _interval_issue(settings, changes)
    if issue is not None:
        db.rollback()
        raise InvalidInputError(issue)
    db.commit()
    return settings


def _interval_issue(settings: AppSettings, changes: dict[str, int]) -> Issue | None:
    """The issue if the timeout is more than half the interval, on the field that was sent
    (the timeout when both were)."""
    interval = settings.check_interval_seconds
    timeout = settings.check_timeout_seconds
    if timeout_fits(interval, timeout):
        return None
    if "check_timeout_seconds" in changes or "check_interval_seconds" not in changes:
        return timeout_too_long(interval)
    return Issue(
        ("check_interval_seconds",),
        f"The check interval must be at least twice the timeout ({2 * timeout} s).",
        "interval_too_short",
    )


def timeout_fits(interval: int, timeout: int) -> bool:
    """The timeout is at most half the interval (owner decision, M6)."""
    return 2 * timeout <= interval


def timeout_too_long(interval: int) -> Issue:
    """The issue for a timeout above half the interval (also used by the import, M8)."""
    return Issue(
        ("check_timeout_seconds",),
        f"The timeout can be at most half the check interval ({interval // 2} s).",
        "timeout_too_long",
    )


def _parse(key: str, raw: str) -> int | None:
    limits = LIMITS[key]
    try:
        value = int(raw.strip())
    except ValueError:
        _report(key, raw, f"not a whole number; using the default {limits.default}")
        return None
    if not limits.low <= value <= limits.high:
        _report(key, raw, f"outside {limits.low}-{limits.high}; using the default {limits.default}")
        return None
    return value


def _report(key: str, raw: str, problem: str) -> None:
    if (key, raw) in _reported:
        return
    _reported.add((key, raw))
    logger.warning("Stored setting %s=%r is %s.", key, raw, problem)
