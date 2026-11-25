"""Devices and their services: the business rules from brief section 6.

Field formats (IP, MAC, hostname, lengths) are checked by the request schemas. This module
checks what depends on other fields or other rows, always on the device as it will be saved
(a partial update is merged with the stored device first), and reports every problem at
once as field issues (decision M3: same shape as FastAPI's validation errors).
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.core.addresses import is_locally_administered
from app.core.timeutil import utcnow
from app.models import Category, CheckType, Device, Service
from app.models.base import name_key
from app.schemas.device import DeviceCreate, DeviceUpdate, PositionsUpdate, ServiceIn
from app.services.errors import InvalidInputError, Issue, NotFoundError
from app.services.oui import OuiDatabase
from app.services.writes import commit

RANDOMIZED_MAC_VENDOR = "Randomized (private) MAC"
NOT_FOUND = "Device not found."

# New devices get the first free cell of this grid (brief section 6), counted row by row from
# the top left. The spacing leaves room for edge labels between nodes of NODE_WIDTH x
# NODE_HEIGHT, the fixed size of a node on the map (frontend/src/lib/topology.ts, keep in sync).
GRID_SPACING_X = 240.0
GRID_SPACING_Y = 140.0
GRID_COLUMNS = 6
NODE_WIDTH = 192.0
NODE_HEIGHT = 56.0

MAX_NAMES_IN_WARNING = 5

# Fields the cross-field rules look at.
_RULE_FIELDS = (
    "name",
    "hostname",
    "ip_address",
    "category_id",
    "check_type",
    "check_enabled",
    "check_port",
)
# Fields that decide what a status check does. Changing one of them, or the check target,
# resets the device's cached status (owner decision, M6).
_CHECK_FIELDS = (
    "check_type",
    "check_enabled",
    "check_port",
    "check_scheme",
    "check_path",
    "check_verify_tls",
)
# (field, warning type): values that other devices may share, with a warning.
_SHARED_FIELDS = (("ip_address", "shared_ip"), ("mac_address", "shared_mac"))


@dataclass(frozen=True)
class SavedDevice:
    device: Device
    warnings: list[Issue]


# --- Reading ---------------------------------------------------------------------------------


def list_devices(db: DbSession) -> list[Device]:
    """All devices, by name. Fine for the brief's "well under 200" devices."""
    return list(
        db.scalars(select(Device).options(selectinload(Device.services)).order_by(Device.name_key))
    )


def get_device(db: DbSession, device_id: str) -> Device:
    device = db.get(Device, device_id, options=[selectinload(Device.services)])
    if device is None:
        raise NotFoundError(NOT_FOUND)
    return device


def check_target(device: Device) -> str | None:
    """Where a status check goes: the IP address if set, otherwise the hostname (M6)."""
    return device.ip_address or device.hostname


def vendor_for_mac(oui: OuiDatabase, mac: str | None) -> str | None:
    """Vendor from the offline IEEE list. Locally administered MACs (phones and laptops use
    random ones for privacy) have no vendor to look up."""
    if mac is None:
        return None
    if is_locally_administered(mac):
        return RANDOMIZED_MAC_VENDOR
    return oui.lookup(mac)


def next_grid_position(db: DbSession) -> tuple[float, float]:
    """Top-left corner of the first grid cell where a new node would not overlap any node.

    Nodes can be dragged anywhere (M5), so a cell is taken by any node whose box overlaps the
    box a node in that cell would have, not only by a node that sits exactly on the grid.
    """
    rows = db.execute(
        select(Device.map_x, Device.map_y).where(
            Device.map_x.is_not(None), Device.map_y.is_not(None)
        )
    )
    return free_grid_cells((x, y) for x, y in rows if x is not None and y is not None)[0]


def free_grid_cells(
    positions: Iterable[tuple[float, float]], count: int = 1
) -> list[tuple[float, float]]:
    """The first ``count`` grid cells where a new node would overlap neither a node at
    ``positions`` (top-left corners) nor one placed in an earlier returned cell. The import
    (M8) places many devices at once with it, so cells taken are kept in a set (a node covers
    at most four cells) instead of comparing every cell with every node."""
    taken: set[tuple[int, int]] = set()
    for x, y in positions:
        if math.isfinite(x) and math.isfinite(y):
            taken.update(_cells_under(x, y))
    cells: list[tuple[float, float]] = []
    index = 0
    while len(cells) < count:  # ends: each node covers at most four cells
        row, column = divmod(index, GRID_COLUMNS)
        if (row, column) not in taken:
            taken.add((row, column))  # a node on a cell covers only that cell
            cells.append((column * GRID_SPACING_X, row * GRID_SPACING_Y))
        index += 1
    return cells


def _cells_under(x: float, y: float) -> set[tuple[int, int]]:
    """Grid cells (row, column) where a new node would overlap a node at (x, y)."""
    columns = range(
        max(0, math.floor((x - NODE_WIDTH) / GRID_SPACING_X)),
        min(GRID_COLUMNS - 1, math.floor((x + NODE_WIDTH) / GRID_SPACING_X)) + 1,
    )
    rows = range(
        max(0, math.floor((y - NODE_HEIGHT) / GRID_SPACING_Y)),
        max(-1, math.floor((y + NODE_HEIGHT) / GRID_SPACING_Y)) + 1,
    )
    return {
        (row, column)
        for row in rows
        for column in columns
        if _overlaps(column * GRID_SPACING_X, row * GRID_SPACING_Y, x, y)
    }


def _overlaps(x1: float, y1: float, x2: float, y2: float) -> bool:
    """Whether two node boxes with these top-left corners overlap (touching is fine)."""
    return abs(x1 - x2) < NODE_WIDTH and abs(y1 - y2) < NODE_HEIGHT


def sharing_warnings(db: DbSession, device: Device) -> list[Issue]:
    """Warnings when another device has the same IP or MAC address (allowed, brief section 6)."""
    warnings: list[Issue] = []
    for field, warning_type in _SHARED_FIELDS:
        value = getattr(device, field)
        if value is None:
            continue
        column = getattr(Device, field)
        names = db.scalars(
            select(Device.name)
            .where(column == value, Device.id != device.id)
            .order_by(Device.name_key)
        ).all()
        if names:
            warnings.append(
                Issue((field,), f"{value} is also used by {_name_list(names)}.", warning_type)
            )
    return warnings


def _name_list(names: Sequence[str]) -> str:
    shown = list(names[:MAX_NAMES_IN_WARNING])
    hidden = len(names) - len(shown)
    if hidden:
        return f"{', '.join(shown)} and {hidden} more"
    if len(shown) == 1:
        return shown[0]
    return f"{', '.join(shown[:-1])} and {shown[-1]}"


# --- Writing ---------------------------------------------------------------------------------


def create_device(db: DbSession, oui: OuiDatabase, data: DeviceCreate) -> SavedDevice:
    values = _column_values(data.model_dump(exclude={"services"}))
    _check_rules(db, values, data.services, device_id=None)

    now = utcnow()
    map_x, map_y = next_grid_position(db)
    device = Device(
        **values,
        vendor=vendor_for_mac(oui, values["mac_address"]),
        map_x=map_x,
        map_y=map_y,
        created_at=now,
        updated_at=now,
    )
    device.services = [_new_service(service) for service in data.services]
    db.add(device)
    commit(
        db,
        not_found=NOT_FOUND,
        recheck=lambda: _check_rules(db, values, data.services, device_id=None),
    )
    return _saved(db, device)


def update_device(
    db: DbSession, oui: OuiDatabase, device_id: str, data: DeviceUpdate
) -> SavedDevice:
    """Partial update; ``services``, if given, replaces the whole list."""
    device = get_device(db, device_id)
    changes = _column_values(data.model_dump(exclude_unset=True, exclude={"services"}))
    services = data.services if "services" in data.model_fields_set else None
    merged = {field: changes.get(field, getattr(device, field)) for field in _RULE_FIELDS}
    _check_rules(db, merged, services, device_id=device.id)

    # The form sends every field (decision M4), so a save without changes sends the stored
    # values: that is not an edit (found in the M7 review).
    edited = any(getattr(device, field) != value for field, value in changes.items()) or (
        services is not None and _service_keys(services) != _service_keys(device.services)
    )
    old_check = _check_settings(device)
    for field, value in changes.items():
        setattr(device, field, value)
    if _check_settings(device) != old_check:
        _reset_status(device)
    if "mac_address" in changes:
        device.vendor = vendor_for_mac(oui, device.mac_address)
    if edited:
        # Set here, not by the column: only user edits count as "recently edited" (M7), also
        # when only services changed; map moves (M5) and status checks (M6) do not.
        device.updated_at = utcnow()

    def replace_services() -> None:
        if services is None:
            return
        # Delete the old rows first: in one flush SQLAlchemy inserts before it deletes, which
        # would trip the (device, port, protocol) unique constraint when a service is kept.
        # This flush also writes the device's changes, so it runs inside commit()'s race
        # handling.
        device.services.clear()
        db.flush()
        device.services.extend(_new_service(service) for service in services)

    def recheck() -> None:
        _require_device(db, device_id)
        _check_rules(db, merged, services, device_id=device_id)

    commit(db, not_found=NOT_FOUND, recheck=recheck, steps=replace_services)
    return _saved(db, device)


def delete_device(db: DbSession, device_id: str) -> None:
    """Deletes its services, links and status history too (ON DELETE CASCADE)."""
    result = db.execute(delete(Device).where(Device.id == device_id))
    db.commit()
    if not getattr(result, "rowcount", 0):
        raise NotFoundError(NOT_FOUND)


def save_positions(db: DbSession, data: PositionsUpdate) -> None:
    """Move nodes on the map. Not an edit: ``updated_at`` stays (decision M3.19).

    All or nothing: a device listed twice or not found (perhaps deleted in another tab) is
    reported on its entry and nothing is saved. Each UPDATE checks its own row count, so a
    device deleted between the check and the write is caught too.
    """
    issues: list[Issue] = []
    seen: set[str] = set()
    for index, position in enumerate(data.positions):
        device_id = str(position.device_id)
        if device_id in seen:
            issues.append(
                Issue(
                    ("positions", index, "device_id"),
                    "This device is listed more than once.",
                    "duplicate_device",
                )
            )
        seen.add(device_id)
    if issues:
        raise InvalidInputError(issues)

    for index, position in enumerate(data.positions):
        result = db.execute(
            update(Device)
            .where(Device.id == str(position.device_id))
            .values(map_x=position.map_x, map_y=position.map_y)
        )
        if not getattr(result, "rowcount", 0):
            issues.append(Issue(("positions", index, "device_id"), NOT_FOUND, "device_not_found"))
    if issues:
        db.rollback()
        raise InvalidInputError(issues)
    db.commit()


def _check_settings(device: Device) -> tuple[object, ...]:
    return (*(getattr(device, field) for field in _CHECK_FIELDS), check_target(device))


_STATUS_RESET: dict[str, object] = {
    "last_checked_at": None,
    "last_is_up": None,
    "last_latency_ms": None,
    "consecutive_failures": 0,
    "last_check_error": None,
}


def _reset_status(device: Device) -> None:
    """The check changed: forget the cached status, so the device shows "Waiting for check"
    and the monitor checks it right away (it looks for checks without a result every few
    seconds). The status history stays until it is purged. The monitor never records a
    result of the old check afterwards (``services.status.record_results``).

    Every column is written, even one that already had the reset value when the device was
    loaded: the monitor may have stored a result since (found in the M6 review).
    """
    for column, value in _STATUS_RESET.items():
        setattr(device, column, value)
        flag_modified(device, column)


def _require_device(db: DbSession, device_id: str) -> None:
    """NotFoundError unless the device exists (queried, not taken from the session)."""
    if db.scalar(select(Device.id).where(Device.id == device_id)) is None:
        raise NotFoundError(NOT_FOUND)


# --- Rules -----------------------------------------------------------------------------------


def _check_rules(
    db: DbSession,
    values: Mapping[str, Any],
    services: Sequence[ServiceIn] | None,
    device_id: str | None,
) -> None:
    """Raise InvalidInputError listing every broken rule. ``values`` is the device as it will
    be saved; ``services`` is None when they do not change."""
    issues: list[Issue] = []

    existing = db.scalars(select(Device).where(Device.name_key == name_key(values["name"]))).first()
    if existing is not None and existing.id != device_id:
        issues.append(
            Issue(("name",), f'A device named "{existing.name}" already exists.', "duplicate_name")
        )

    category_id = values["category_id"]
    found = db.scalar(select(Category.id).where(Category.id == category_id))
    if category_id is not None and found is None:
        issues.append(
            Issue(("category_id",), "This category does not exist.", "category_not_found")
        )

    issues.extend(device_rule_issues(values, services))
    if issues:
        raise InvalidInputError(issues)


def device_rule_issues(
    values: Mapping[str, Any], services: Sequence[ServiceIn] | None
) -> list[Issue]:
    """The rules that need no database: check settings and duplicate services. Shared with
    the import (M8), which checks every device of a file against them; ``loc`` is relative to
    the device."""
    issues: list[Issue] = []
    check_type = CheckType(values["check_type"])
    if values["check_enabled"]:
        if check_type == CheckType.NONE:
            issues.append(
                Issue(
                    ("check_type",),
                    "Choose a check type to turn the check on.",
                    "check_type_required",
                )
            )
        if not values["ip_address"] and not values["hostname"]:
            issues.append(
                Issue(
                    ("check_enabled",),
                    "A check needs an IP address or a hostname.",
                    "check_target_required",
                )
            )
    if check_type == CheckType.TCP and values["check_port"] is None:
        issues.append(Issue(("check_port",), "A TCP check needs a port.", "check_port_required"))

    if services is not None:
        seen: set[tuple[int, str]] = set()
        for index, service in enumerate(services):
            key = (service.port, service.protocol.value)
            if key in seen:
                issues.append(
                    Issue(
                        ("services", index, "port"),
                        f"{service.port}/{service.protocol.value} is already listed on this "
                        "device.",
                        "duplicate_service",
                    )
                )
            seen.add(key)
    return issues


def _column_values(dumped: Mapping[str, Any]) -> dict[str, Any]:
    """Schema output -> column values (UUIDs are stored as strings)."""
    values = dict(dumped)
    if values.get("category_id") is not None:
        values["category_id"] = str(values["category_id"])
    return values


def _service_keys(
    services: Sequence[ServiceIn | Service],
) -> list[tuple[int, str, str, str | None]]:
    """What a service list holds, in a fixed order (the ids change on every save)."""
    return sorted(
        (service.port, str(service.protocol), service.name, service.note) for service in services
    )


def _new_service(service: ServiceIn) -> Service:
    return Service(
        port=service.port, protocol=service.protocol, name=service.name, note=service.note
    )


def _saved(db: DbSession, device: Device) -> SavedDevice:
    db.refresh(device, attribute_names=["services"])  # reload in port order
    return SavedDevice(device=device, warnings=sharing_warnings(db, device))
