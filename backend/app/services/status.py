"""Status checks (M6): which devices to check, recording results, the cached status, the
purge of old history.

The monitor (``app/monitor``) runs the checks; everything it reads or writes goes through
this module. Status writes never touch ``updated_at``: a check is not an edit (decision
M3.19).
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session as DbSession

from app.core.timeutil import utcnow
from app.models import CheckScheme, CheckType, Device, DeviceStatus, StatusCheck
from app.models.device import LAST_CHECK_ERROR_LENGTH
from app.services.app_settings import AppSettings, get_settings
from app.services.devices import check_target

logger = logging.getLogger("netscope.monitor")

# A result older than this many intervals (plus the timeout) no longer counts: if the monitor
# stopped checking, a device must not stay green (owner decision, M6).
STALE_AFTER_INTERVALS = 3


@dataclass(frozen=True)
class CheckJob:
    """A device's check as it was when it was read. Its result is recorded only if the device
    still has this check and nobody else wrote a status since (see ``record_results``)."""

    device_id: str
    name: str
    check_type: CheckType
    target: str
    port: int | None
    scheme: CheckScheme
    path: str
    verify_tls: bool
    # The status the job was read with: a reset (check changed) or another write changes it.
    last_checked_at: datetime | None


@dataclass(frozen=True)
class CheckResult:
    is_up: bool
    latency_ms: float | None  # None when the check failed
    error: str | None  # why it failed, shown to the user; None when it succeeded
    checked_at: datetime


@dataclass(frozen=True)
class Transition:
    """A device's status changed to up or down (logged by the monitor)."""

    name: str
    status: DeviceStatus
    error: str | None


@dataclass(frozen=True)
class StatusView:
    """What ``status_of`` needs besides the device."""

    settings: AppSettings
    now: datetime


# --- Reading ---------------------------------------------------------------------------------


def status_view(db: DbSession, settings: AppSettings | None = None) -> StatusView:
    return StatusView(settings=settings or get_settings(db), now=utcnow())


def status_of(device: Device, view: StatusView) -> DeviceStatus:
    if not device.check_enabled or device.check_type == CheckType.NONE:
        return DeviceStatus.OFF
    if device.last_checked_at is None or device.last_is_up is None:
        return DeviceStatus.WAITING
    if view.now - device.last_checked_at > stale_after(view.settings):
        return DeviceStatus.STALE
    return DeviceStatus.UP if device.last_is_up else DeviceStatus.DOWN


def stale_after(settings: AppSettings) -> timedelta:
    return timedelta(
        seconds=STALE_AFTER_INTERVALS * settings.check_interval_seconds
        + settings.check_timeout_seconds
    )


def checks_to_run(db: DbSession, *, only_new: bool = False) -> list[CheckJob]:
    """Every device whose check is on (``only_new``: only those without a result yet, which
    the monitor checks right away)."""
    statement = select(Device).where(
        Device.check_enabled.is_(True), Device.check_type != CheckType.NONE
    )
    if only_new:
        statement = statement.where(Device.last_checked_at.is_(None))
    jobs: list[CheckJob] = []
    for device in db.scalars(statement.order_by(Device.name_key)):
        target = check_target(device)
        if target is None:  # the device rules forbid it; never check an empty target
            continue
        jobs.append(
            CheckJob(
                device_id=device.id,
                name=device.name,
                check_type=device.check_type,
                target=target,
                port=device.check_port,
                scheme=device.check_scheme,
                path=device.check_path,
                verify_tls=device.check_verify_tls,
                last_checked_at=device.last_checked_at,
            )
        )
    return jobs


# --- Writing ---------------------------------------------------------------------------------


def record_results(
    db: DbSession,
    results: Sequence[tuple[CheckJob, CheckResult]],
    failures_before_down: int,
) -> list[Transition]:
    """Store one round's results in one transaction: the cached status on each device and a
    history row per check.

    A device shows as down only after ``failures_before_down`` failed checks in a row (brief
    section 6); until then it keeps its previous status. A result is skipped when the device
    was deleted, its check changed (which resets the status) or another write came first
    since the job was read: each UPDATE compares the check settings and ``last_checked_at``
    with the job's and must hit exactly one row.
    """
    transitions: list[Transition] = []
    for job, result in results:
        current = db.execute(
            select(Device.last_is_up, Device.consecutive_failures).where(Device.id == job.device_id)
        ).one_or_none()
        if current is None:
            continue
        was_up, failures = current
        is_up: bool | None
        if result.is_up:
            failures, is_up = 0, True
        else:
            failures += 1
            is_up = False if failures >= failures_before_down else was_up
        error = None if result.is_up else _short(result.error or "Check failed.")
        updated = db.execute(
            update(Device)
            .where(
                Device.id == job.device_id,
                Device.check_enabled.is_(True),
                Device.check_type == job.check_type,
                func.coalesce(Device.ip_address, Device.hostname) == job.target,
                Device.check_port.is_(job.port),
                Device.check_scheme == job.scheme,
                Device.check_path == job.path,
                Device.check_verify_tls.is_(job.verify_tls),
                Device.last_checked_at.is_(job.last_checked_at),
                Device.last_is_up.is_(was_up),
            )
            .values(
                last_checked_at=result.checked_at,
                last_is_up=is_up,
                last_latency_ms=result.latency_ms if result.is_up else None,
                consecutive_failures=failures,
                last_check_error=error,
            )
            .execution_options(synchronize_session=False)
        )
        if getattr(updated, "rowcount", 0) != 1:
            continue
        db.execute(
            insert(StatusCheck).values(
                device_id=job.device_id,
                checked_at=result.checked_at,
                is_up=result.is_up,
                latency_ms=result.latency_ms if result.is_up else None,
            )
        )
        if is_up is False and was_up is not False:
            transitions.append(Transition(job.name, DeviceStatus.DOWN, error))
        elif is_up is True and was_up is False:
            transitions.append(Transition(job.name, DeviceStatus.UP, None))
    db.commit()
    return transitions


def purge_history(db: DbSession, older_than: datetime, batch_size: int) -> int:
    """Delete at most ``batch_size`` history rows checked before ``older_than``, in their own
    short transaction (uses the ``checked_at`` index). Returns how many were deleted; the
    monitor repeats until a batch is not full, pausing in between so a large purge never
    holds SQLite's write lock for long."""
    oldest = (
        select(StatusCheck.id)
        .where(StatusCheck.checked_at < older_than)
        .order_by(StatusCheck.checked_at)
        .limit(batch_size)
    )
    result = db.execute(
        delete(StatusCheck)
        .where(StatusCheck.id.in_(oldest.scalar_subquery()))
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return int(getattr(result, "rowcount", 0))


def _short(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= LAST_CHECK_ERROR_LENGTH:
        return text
    return text[: LAST_CHECK_ERROR_LENGTH - 1].rstrip() + "…"
