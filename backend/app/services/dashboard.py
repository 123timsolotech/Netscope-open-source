"""Dashboard numbers (M7): computed from the database on every request, never stored and
never hardcoded (brief section 10).

Every number about devices comes from one statement (devices joined with their category),
so they agree with each other even while another request writes: SQLite gives each
statement its own snapshot, and pysqlite starts no transaction for plain reads. A second
statement only adds the categories without devices. Each device's status is M6's
``status_of``, so the device list, the map and the dashboard always show the same status.
"""

from collections import Counter
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.models import Category, Device, DeviceStatus, Link, Service
from app.services.categories import CategoryInfo
from app.services.status import StatusView, stale_after, status_of, status_view

# How many devices "Recently edited" lists (owner decision, M7; no time window).
RECENT_LIMIT = 5


@dataclass(frozen=True)
class Dashboard:
    device_count: int
    status_counts: dict[DeviceStatus, int]  # every status, zeros included
    first_results_pending: bool
    categories: list[CategoryInfo]  # every category, most devices first, then by name
    uncategorized_count: int
    recently_edited: list[Device]  # newest first
    down: list[Device]  # by name
    link_count: int
    service_count: int
    monitor_quiet_seconds: int | None  # see monitor_quiet()


def never_edited(device: Device) -> bool:
    """Added and not edited since: the service layer sets both times at once on create."""
    return device.updated_at == device.created_at


def monitor_quiet(
    view: StatusView, checks_on: bool, monitor_idle_seconds: float | None
) -> int | None:
    """Seconds the monitor has been quiet, when that looks stuck (owner decision, M8): a check
    is on and no round finished for longer than the "No recent check" limit (3 intervals plus
    the timeout). Unlike "every checked device has no recent check", this also catches a
    monitor that stopped before the first results (those devices stay "Waiting"). None when
    the app runs without a monitor (tests)."""
    if not checks_on or monitor_idle_seconds is None:
        return None
    if monitor_idle_seconds <= stale_after(view.settings).total_seconds():
        return None
    return int(monitor_idle_seconds)


def get_dashboard(
    db: DbSession, view: StatusView | None = None, *, monitor_idle_seconds: float | None = None
) -> Dashboard:
    """``monitor_idle_seconds``: how long ago the status monitor last finished a round (or
    started), from ``Monitor.seconds_since_progress``; None without a monitor."""
    view = view or status_view(db)
    # Well under 200 devices (brief section 12): one statement, counted here. Services are
    # not needed.
    rows = db.execute(
        select(Device, Category)
        .outerjoin(Category, Device.category_id == Category.id)
        .order_by(Device.name_key)
    ).all()
    devices = [device for device, _category in rows]
    statuses = {device.id: status_of(device, view) for device in devices}
    status_counts = Counter(statuses.values())

    categories = {category.id: category for _device, category in rows if category is not None}
    for category in db.scalars(select(Category)):
        categories.setdefault(category.id, category)  # one without devices
    category_counts = Counter(category.id for _device, category in rows if category is not None)
    totals = db.execute(
        select(
            select(func.count()).select_from(Link).scalar_subquery().label("link_count"),
            select(func.count()).select_from(Service).scalar_subquery().label("service_count"),
        )
    ).one()

    return Dashboard(
        device_count=len(devices),
        status_counts={status: status_counts[status] for status in DeviceStatus},
        first_results_pending=any(
            statuses[device.id] == DeviceStatus.WAITING and device.last_checked_at is None
            for device in devices
        ),
        categories=sorted(
            (
                CategoryInfo(category, category_counts[category.id])
                for category in categories.values()
            ),
            key=lambda info: (-info.device_count, info.category.name_key),
        ),
        uncategorized_count=sum(1 for _device, category in rows if category is None),
        # Python's sort is stable and the rows are by name, so devices edited at the same
        # moment stay in name order.
        recently_edited=sorted(devices, key=lambda device: device.updated_at, reverse=True)[
            :RECENT_LIMIT
        ],
        down=[device for device in devices if statuses[device.id] == DeviceStatus.DOWN],
        # One more statement: a write in between can make these a poll late, never wrong.
        link_count=totals.link_count,
        service_count=totals.service_count,
        monitor_quiet_seconds=monitor_quiet(
            view,
            any(statuses[device.id] != DeviceStatus.OFF for device in devices),
            monitor_idle_seconds,
        ),
    )
