"""Device CRUD, services included (session required)."""

from uuid import UUID

from fastapi import APIRouter
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from app.api.deps import Db, Oui
from app.models import Device
from app.schemas.common import IssueOut
from app.schemas.device import (
    DeviceCreate,
    DeviceOut,
    DeviceSaved,
    DeviceUpdate,
    PositionsUpdate,
)
from app.services import devices as device_service
from app.services import status as status_service
from app.services.devices import SavedDevice
from app.services.status import StatusView

router = APIRouter(prefix="/devices", tags=["devices"])


def _out(device: Device, view: StatusView) -> DeviceOut:
    return DeviceOut.model_validate(device).model_copy(
        update={"status": status_service.status_of(device, view)}
    )


def _saved(db: Db, result: SavedDevice) -> DeviceSaved:
    device = _out(result.device, status_service.status_view(db))
    return DeviceSaved(
        **device.model_dump(), warnings=[IssueOut.of(issue) for issue in result.warnings]
    )


@router.get("")
def list_devices(db: Db) -> list[DeviceOut]:
    devices = device_service.list_devices(db)
    view = status_service.status_view(db)
    return [_out(device, view) for device in devices]


@router.put("/positions", status_code=HTTP_204_NO_CONTENT)
def save_positions(body: PositionsUpdate, db: Db) -> None:
    """Move devices on the map (M5). All or nothing; does not count as an edit."""
    device_service.save_positions(db, body)


@router.get("/{device_id}")
def get_device(device_id: UUID, db: Db) -> DeviceOut:
    device = device_service.get_device(db, str(device_id))
    return _out(device, status_service.status_view(db))


@router.post("", status_code=HTTP_201_CREATED)
def create_device(body: DeviceCreate, db: Db, oui: Oui) -> DeviceSaved:
    return _saved(db, device_service.create_device(db, oui, body))


@router.patch("/{device_id}")
def update_device(device_id: UUID, body: DeviceUpdate, db: Db, oui: Oui) -> DeviceSaved:
    """Partial update. Fields left out stay unchanged; ``services`` replaces the list."""
    return _saved(db, device_service.update_device(db, oui, str(device_id), body))


@router.delete("/{device_id}", status_code=HTTP_204_NO_CONTENT)
def delete_device(device_id: UUID, db: Db) -> None:
    """Also deletes the device's services, links and status history."""
    device_service.delete_device(db, str(device_id))
