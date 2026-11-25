"""UTC time helpers.

The brief (section 6): timestamps are UTC, stored without a timezone (SQLite keeps none)
and returned by the API as ISO 8601 with ``Z``.
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Current UTC time as a naive datetime, the form stored in the database."""
    return datetime.now(UTC).replace(tzinfo=None)


def to_iso_z(value: datetime) -> str:
    """Format a datetime as ISO 8601 UTC with a trailing ``Z``.

    Naive values are taken to be UTC (that is how they are stored). Aware values are
    converted to UTC first.
    """
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.isoformat(timespec="milliseconds") + "Z"
