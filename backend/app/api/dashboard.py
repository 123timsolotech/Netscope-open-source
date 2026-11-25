"""The dashboard's numbers (M7, session required)."""

from fastapi import APIRouter, Request

from app.api.deps import Db
from app.models import Device
from app.monitor.scheduler import Monitor
from app.schemas.dashboard import (
    DashboardCategory,
    DashboardOut,
    DownDevice,
    RecentDevice,
    StatusCounts,
)
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _recent(device: Device) -> RecentDevice:
    return RecentDevice(
        id=device.id,
        name=device.name,
        category_id=device.category_id,
        created_at=device.created_at,
        updated_at=device.updated_at,
        added=dashboard_service.never_edited(device),
    )


def _down(device: Device) -> DownDevice:
    return DownDevice(
        id=device.id,
        name=device.name,
        category_id=device.category_id,
        last_check_error=device.last_check_error,
        last_checked_at=device.last_checked_at,
    )


@router.get("")
def get_dashboard(db: Db, request: Request) -> DashboardOut:
    """Device totals, status counts, counts by category, recently edited and down devices,
    computed from the database on every request; plus whether the monitor looks stuck."""
    monitor: Monitor | None = getattr(request.app.state, "monitor", None)
    data = dashboard_service.get_dashboard(
        db, monitor_idle_seconds=None if monitor is None else monitor.seconds_since_progress()
    )
    return DashboardOut(
        device_count=data.device_count,
        status_counts=StatusCounts(**{str(k): v for k, v in data.status_counts.items()}),
        first_results_pending=data.first_results_pending,
        categories=[
            DashboardCategory(
                id=info.category.id,
                name=info.category.name,
                color=info.category.color,
                icon=info.category.icon,
                device_count=info.device_count,
            )
            for info in data.categories
        ],
        uncategorized_count=data.uncategorized_count,
        recently_edited=[_recent(device) for device in data.recently_edited],
        down=[_down(device) for device in data.down],
        link_count=data.link_count,
        service_count=data.service_count,
        monitor_quiet_seconds=data.monitor_quiet_seconds,
    )
