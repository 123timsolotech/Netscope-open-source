"""Response shape of the dashboard (M7). Read-only: there is nothing to send."""

from pydantic import BaseModel

from app.schemas.common import UtcDateTime


class StatusCounts(BaseModel):
    """How many devices have each status (the words are the frontend's, M6)."""

    up: int
    down: int
    waiting: int
    stale: int
    off: int


class DashboardCategory(BaseModel):
    id: str
    name: str
    color: str
    icon: str
    device_count: int


class RecentDevice(BaseModel):
    id: str
    name: str
    category_id: str | None
    created_at: UtcDateTime
    updated_at: UtcDateTime
    # Never edited since it was created: the dashboard says "Added" instead of "Edited".
    added: bool


class DownDevice(BaseModel):
    id: str
    name: str
    category_id: str | None
    last_check_error: str | None
    last_checked_at: UtcDateTime | None


class DashboardOut(BaseModel):
    device_count: int
    status_counts: StatusCounts
    # A device whose check was just turned on or changed has no result yet: the page polls
    # every 5 s until it has one, like the device list (decision M6.10).
    first_results_pending: bool
    # Every category, most devices first, then by name (empty ones too: the page counts them).
    categories: list[DashboardCategory]
    uncategorized_count: int
    # The most recently added or edited devices, newest first (owner decision, M7: 5).
    recently_edited: list[RecentDevice]
    # Every device that is down, by name.
    down: list[DownDevice]
    # Totals (owner decision, M8): links between devices, services on all devices.
    link_count: int
    service_count: int
    # Seconds since the status monitor last finished a round, when a check is on and that is
    # longer than the "No recent check" limit (3 intervals plus the timeout); otherwise null.
    # The page then warns that the monitor may be stuck (owner decision, M8).
    monitor_quiet_seconds: int | None
