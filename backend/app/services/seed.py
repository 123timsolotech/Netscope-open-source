"""``netscope seed``: default categories and optional demo data.

Never overwrites or duplicates: a default category or demo device whose name already exists
(in any letter case) is left alone. Demo data goes through the same services and validation
as the API.
"""

import math
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.models import Category, Device
from app.models.base import name_key
from app.schemas.device import MAP_COORDINATE_LIMIT, DeviceCreate, PositionsUpdate
from app.schemas.link import LinkCreate
from app.services import devices as device_service
from app.services import links as link_service
from app.services.oui import OuiDatabase
from app.services.seed_data import DEFAULT_CATEGORIES, DEMO_DEVICES, DEMO_LINKS, DEMO_POSITIONS

MAP_SNAP = 20  # the map's snap grid (frontend/src/lib/topology.ts)


@dataclass
class DemoResult:
    devices_added: list[str] = field(default_factory=list)
    devices_skipped: list[str] = field(default_factory=list)
    links_added: int = 0


def add_missing_default_categories(db: DbSession) -> list[str]:
    """Add the default categories whose names do not exist yet. Returns the names added."""
    existing = set(db.scalars(select(Category.name_key)))
    added = [
        default.name for default in DEFAULT_CATEGORIES if name_key(default.name) not in existing
    ]
    for default in DEFAULT_CATEGORIES:
        if default.name in added:
            db.add(Category(name=default.name, color=default.color, icon=default.icon))
    db.commit()
    return added


def add_demo_data(db: DbSession, oui: OuiDatabase) -> DemoResult:
    """Add the demo devices (checks configured but off) and the links between them.

    Links are only made between demo devices added in this run, never to a device the user
    already has under a demo name. The added devices get the demo map layout, below any
    devices that were already on the map.
    """
    add_missing_default_categories(db)
    category_ids = {key: id_ for id_, key in db.execute(select(Category.id, Category.name_key))}
    result = DemoResult()
    offset_y = _space_below_existing_devices(db)

    for spec in DEMO_DEVICES:
        name = spec["name"]
        if _device_id(db, name) is not None:
            result.devices_skipped.append(name)
            continue
        fields = {key: value for key, value in spec.items() if key != "category"}
        fields["category_id"] = category_ids.get(name_key(spec["category"]))
        device_service.create_device(db, oui, DeviceCreate.model_validate(fields))
        result.devices_added.append(name)

    added = set(result.devices_added)
    for name_a, name_b, link_type, label in DEMO_LINKS:
        if name_a not in added or name_b not in added:
            continue
        id_a, id_b = _device_id(db, name_a), _device_id(db, name_b)
        if id_a is None or id_b is None:  # cannot happen: just added
            continue
        link_service.create_link(
            db,
            LinkCreate.model_validate(
                {"device_a_id": id_a, "device_b_id": id_b, "link_type": link_type, "label": label}
            ),
        )
        result.links_added += 1

    positions = [
        {"device_id": _device_id(db, name), "map_x": x, "map_y": y + offset_y}
        for name, (x, y) in DEMO_POSITIONS.items()
        if name in added
    ]
    # A map that already reaches the coordinate limit leaves no room below it: the demo
    # devices then keep the free grid cells they got when they were created.
    fits = offset_y + max(y for _x, y in DEMO_POSITIONS.values()) <= MAP_COORDINATE_LIMIT
    if positions and fits:
        device_service.save_positions(db, PositionsUpdate.model_validate({"positions": positions}))
    return result


def _space_below_existing_devices(db: DbSession) -> float:
    """How far to shift the demo layout down so it starts below every device on the map
    (0 on an empty map), rounded up to the map's 20 px snap grid."""
    lowest = db.scalar(select(func.max(Device.map_y)))
    if lowest is None:
        return 0.0
    bottom = lowest + device_service.NODE_HEIGHT + device_service.GRID_SPACING_Y
    return float(math.ceil(bottom / MAP_SNAP) * MAP_SNAP)


def _device_id(db: DbSession, name: str) -> str | None:
    return db.scalar(select(Device.id).where(Device.name_key == name_key(name)))
