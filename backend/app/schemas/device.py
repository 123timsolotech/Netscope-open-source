"""Request and response shapes for devices and their services (brief section 6).

Field formats are checked here (IP, MAC, hostname, lengths). Rules that depend on other
fields or on the database (unique names, check settings, duplicate services) live in
``app/services/devices.py``, because a partial update must be checked against the stored
device.
"""

from typing import Annotated
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    Strict,
    StrictBool,
)
from pydantic_core import PydanticCustomError

from app.core.addresses import hostname_problem, normalize_ip, normalize_mac
from app.models import CheckScheme, CheckType, DeviceStatus, Protocol
from app.schemas.common import (
    IssueOut,
    RequestModel,
    Text,
    UtcDateTime,
    blank_to_none,
    omittable,
)

DEVICE_NAME_MAX_LENGTH = 100
SHORT_TEXT_MAX_LENGTH = 100
DESCRIPTION_MAX_LENGTH = 10_000
SERVICE_NOTE_MAX_LENGTH = 2_000
CHECK_PATH_MAX_LENGTH = 2048
MAX_SERVICES_PER_DEVICE = 200
# Map coordinates (M5): far beyond any home network's map, small enough to stay exact.
MAP_COORDINATE_LIMIT = 100_000.0
MAX_POSITIONS_PER_REQUEST = 500


def _ip(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return normalize_ip(value)
    except ValueError as error:
        raise PydanticCustomError("ip_address", str(error)) from None


def _mac(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return normalize_mac(value)
    except ValueError as error:
        raise PydanticCustomError("mac_address", str(error)) from None


def _hostname(value: str | None) -> str | None:
    if value is None:
        return None
    problem = hostname_problem(value)
    if problem:
        raise PydanticCustomError("hostname", problem)
    return value


def _blank_path_is_root(value: object) -> object:
    """An empty path field means the default, ``/``."""
    return "/" if isinstance(value, str) and not value.strip() else value


def _check_path(value: str) -> str:
    # "//host/x" (and "/\\host/x", which browsers and some URL parsers read the same way)
    # would point a check at another host once M6 joins the path to the device's address.
    if (
        not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
        or any(ch.isspace() for ch in value)
    ):
        raise PydanticCustomError(
            "check_path",
            "Start the path with a single / and leave out spaces and backslashes "
            "(for example /health).",
        )
    return value


# JSON numbers only: lax mode would turn true into port 1 and "80" into 80.
Port = Annotated[int, Strict(), Field(ge=1, le=65535)]
DeviceName = Annotated[str, Text(DEVICE_NAME_MAX_LENGTH)]
# 254: a 253-character name plus the optional trailing dot; hostname_problem checks 253.
Hostname = Annotated[str | None, Text(254, optional=True), AfterValidator(_hostname)]
IpAddress = Annotated[str | None, Text(64, optional=True), AfterValidator(_ip)]
MacAddress = Annotated[str | None, Text(32, optional=True), AfterValidator(_mac)]
OptionalId = Annotated[UUID | None, BeforeValidator(blank_to_none)]
ShortText = Annotated[str | None, Text(SHORT_TEXT_MAX_LENGTH, optional=True)]
# A JSON number (int or float, not a bool or a string), finite, within the limit. Python's JSON
# parser accepts NaN and Infinity, which the CHECK-free REAL column would store.
MapCoordinate = Annotated[
    float,
    Strict(),
    Field(ge=-MAP_COORDINATE_LIMIT, le=MAP_COORDINATE_LIMIT, allow_inf_nan=False),
]
Description = Annotated[str | None, Text(DESCRIPTION_MAX_LENGTH, multiline=True, optional=True)]
CheckPath = Annotated[
    str,
    Text(CHECK_PATH_MAX_LENGTH),
    BeforeValidator(_blank_path_is_root),
    AfterValidator(_check_path),
]


class ServiceIn(RequestModel):
    port: Port
    protocol: Protocol = Protocol.TCP
    name: Annotated[str, Text(SHORT_TEXT_MAX_LENGTH)]
    note: Annotated[str | None, Text(SERVICE_NOTE_MAX_LENGTH, multiline=True, optional=True)] = None


ServiceList = Annotated[list[ServiceIn], Field(max_length=MAX_SERVICES_PER_DEVICE)]


class DeviceCreate(RequestModel):
    name: DeviceName
    hostname: Hostname = None
    ip_address: IpAddress = None
    mac_address: MacAddress = None
    category_id: OptionalId = None
    role: ShortText = None
    location: ShortText = None
    description: Description = None
    check_type: CheckType = CheckType.NONE
    check_enabled: StrictBool = False
    check_port: Port | None = None
    check_scheme: CheckScheme = CheckScheme.HTTP
    check_path: CheckPath = "/"
    check_verify_tls: StrictBool = False
    services: ServiceList = Field(default_factory=list)


class DeviceUpdate(RequestModel):
    """Partial update: fields left out stay unchanged; null clears a field that can be empty.

    ``services``, if given, replaces the device's services as a whole. The vendor follows the
    MAC address; the map position has its own endpoint (``PUT /api/devices/positions``).
    """

    # omittable(): may be left out, but null is rejected (these columns cannot be empty).
    name: DeviceName = omittable()
    hostname: Hostname = None
    ip_address: IpAddress = None
    mac_address: MacAddress = None
    category_id: OptionalId = None
    role: ShortText = None
    location: ShortText = None
    description: Description = None
    check_type: CheckType = omittable()
    check_enabled: StrictBool = omittable()
    check_port: Port | None = None
    check_scheme: CheckScheme = omittable()
    check_path: CheckPath = omittable()
    check_verify_tls: StrictBool = omittable()
    services: ServiceList = omittable()


class PositionIn(RequestModel):
    device_id: UUID
    map_x: MapCoordinate
    map_y: MapCoordinate


class PositionsUpdate(RequestModel):
    """New map positions for some devices (M5). Moving a node is not an edit: it does not
    change ``updated_at``. All are checked before any is saved."""

    positions: Annotated[
        list[PositionIn], Field(min_length=1, max_length=MAX_POSITIONS_PER_REQUEST)
    ]


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    port: int
    protocol: Protocol
    name: str
    note: str | None


class DeviceOut(BaseModel):
    # The API layer fills in ``status`` (it needs the settings); the schema still lists it as
    # always present in answers.
    model_config = ConfigDict(
        from_attributes=True, json_schema_serialization_defaults_required=True
    )

    id: str
    name: str
    hostname: str | None
    ip_address: str | None
    mac_address: str | None
    vendor: str | None
    category_id: str | None
    role: str | None
    location: str | None
    description: str | None
    map_x: float | None
    map_y: float | None
    created_at: UtcDateTime
    updated_at: UtcDateTime
    check_type: CheckType
    check_enabled: bool
    check_port: int | None
    check_scheme: CheckScheme
    check_path: str
    check_verify_tls: bool
    last_checked_at: UtcDateTime | None
    last_is_up: bool | None
    last_latency_ms: float | None
    consecutive_failures: int
    last_check_error: str | None
    # Off, waiting, up, down or stale ("No recent check"), computed from the cached status and
    # the settings (owner decision, M6), so the list, the map and the dashboard agree.
    status: DeviceStatus = DeviceStatus.OFF
    services: list[ServiceOut]


class DeviceSaved(DeviceOut):
    """Response to create and update: the device plus warnings (for example a shared IP).

    Warnings have the same shape as validation errors, but the device was saved.
    """

    warnings: list[IssueOut]
