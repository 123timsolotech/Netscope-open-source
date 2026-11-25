"""JSON export and import (M8; brief section 9 "Export format", section 4 "Release decisions").

The export file holds what the user entered: categories, devices with their services, links
and the status-check settings they changed. Never the password, sessions, the status history
or the latest status. ``schema_version`` changes only when the format changes in a way an
older NetScope cannot read; an import refuses versions it does not know.

``ExportFile`` is what ``GET /api/export`` answers. ``ImportFile`` is the same shape as a
request: the forms' rules (``Text``, strict numbers, address formats), no unknown fields, and
limits on the counts. ``POST /api/import`` takes the file's JSON as it is and checks the
``format`` and ``schema_version`` first (``services/backup.py``), so a wrong file gets one
clear message instead of a page of field errors.
"""

import enum
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field, StrictBool, StrictInt
from pydantic_core import PydanticCustomError

from app.models import CheckScheme, CheckType, LinkType, Protocol
from app.schemas.category import CategoryName, Color, IconName
from app.schemas.common import RequestModel, Text, UtcDateTime
from app.schemas.device import (
    CheckPath,
    Description,
    DeviceName,
    Hostname,
    IpAddress,
    MacAddress,
    MapCoordinate,
    OptionalId,
    Port,
    ServiceList,
    ShortText,
)
from app.schemas.link import LinkLabel
from app.schemas.settings import CheckInterval, CheckTimeout, FailuresBeforeDown, RetentionDays

EXPORT_FORMAT: Literal["netscope-export"] = "netscope-export"
SCHEMA_VERSION = 1
# Far above a home network (brief section 12: well under 200 devices), low enough that a
# hostile file cannot make the import work for minutes (owner decision, M8).
MAX_IMPORT_CATEGORIES = 500
MAX_IMPORT_DEVICES = 2_000
MAX_IMPORT_LINKS = 10_000
# Services of all devices together (each device may list 200): without it a 1 MB file of
# 2,000 devices with 200 empty services each gave 800,000 problems, a 75 MB answer and a
# 1.2 GB peak (found in the M8 review).
MAX_IMPORT_SERVICES = 20_000
# Problems listed in one answer; one more item says how many were left out.
MAX_REPORTED_ISSUES = 200
# Request body limit of POST /api/import, with a session (owner decision, M8). A well-filled
# export of 200 devices is about 1 MB. Without a session the usual 32 KiB apply.
IMPORT_BODY_LIMIT = 10 * 1024 * 1024
VENDOR_MAX_LENGTH = 255
# Device names listed in an import's result (added, updated), each.
MAX_LISTED_NAMES = 20


def _naive_utc(value: datetime) -> datetime:
    """A time as the database keeps it: naive UTC. An aware time is converted; a naive one is
    taken to be UTC, as the API returns them. A time that leaves the years 1-9999 when
    converted ("0001-01-01T00:00:00+01:00") is a 422 here, also in a dry run, instead of
    failing while the import writes (found in the M8 review)."""
    if value.tzinfo is None:
        return value
    try:
        return value.astimezone(UTC).replace(tzinfo=None)
    except OverflowError:
        raise PydanticCustomError(
            "datetime_out_of_range", "Use a time between the years 1 and 9999 (in UTC)."
        ) from None


# A device's created_at / updated_at in an import file, converted to naive UTC.
ImportTime = Annotated[datetime, AfterValidator(_naive_utc)]


class ImportMode(enum.StrEnum):
    # Delete every device, category and link, then write the file (the default).
    REPLACE = "replace"
    # The file wins for names that exist; nothing is deleted.
    MERGE = "merge"


# --- Export (response) -------------------------------------------------------------------------


class ExportCategory(BaseModel):
    id: str
    name: str
    color: str
    icon: str


class ExportService(BaseModel):
    port: int
    protocol: Protocol
    name: str
    note: str | None


class ExportDevice(BaseModel):
    id: str
    name: str
    hostname: str | None
    ip_address: str | None
    mac_address: str | None
    # For reading only: an import looks the vendor up again from the MAC.
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
    services: list[ExportService]


class ExportLink(BaseModel):
    id: str
    device_a_id: str
    device_b_id: str
    link_type: LinkType
    label: str | None


class ExportFile(BaseModel):
    format: Literal["netscope-export"] = EXPORT_FORMAT
    schema_version: int = SCHEMA_VERSION
    app_version: str
    exported_at: UtcDateTime
    # Only the settings the user changed (key -> value); the others follow the defaults.
    settings: dict[str, int]
    categories: list[ExportCategory]
    devices: list[ExportDevice]
    links: list[ExportLink]


# --- Import (request) --------------------------------------------------------------------------


class ImportSettings(RequestModel):
    """Left out or null: the default. Replace all stores exactly these; merge ignores them."""

    check_interval_seconds: CheckInterval | None = None
    check_timeout_seconds: CheckTimeout | None = None
    failures_before_down: FailuresBeforeDown | None = None
    retention_days: RetentionDays | None = None


class ImportCategory(RequestModel):
    id: UUID
    name: CategoryName
    color: Color
    icon: IconName


class ImportDevice(RequestModel):
    """A device as ``DeviceCreate`` takes it, plus its id (links and nothing else refer to
    it), map position and times. Left out: the import's defaults (no position: a free grid
    cell; no times: the time of the import)."""

    id: UUID
    name: DeviceName
    hostname: Hostname = None
    ip_address: IpAddress = None
    mac_address: MacAddress = None
    # Accepted (exports contain it) and ignored: recomputed from the MAC address.
    vendor: Annotated[str | None, Text(VENDOR_MAX_LENGTH, optional=True)] = None
    category_id: OptionalId = None
    role: ShortText = None
    location: ShortText = None
    description: Description = None
    map_x: MapCoordinate | None = None
    map_y: MapCoordinate | None = None
    created_at: ImportTime | None = None
    updated_at: ImportTime | None = None
    check_type: CheckType = CheckType.NONE
    check_enabled: StrictBool = False
    check_port: Port | None = None
    check_scheme: CheckScheme = CheckScheme.HTTP
    check_path: CheckPath = "/"
    check_verify_tls: StrictBool = False
    services: ServiceList = Field(default_factory=list)


class ImportLink(RequestModel):
    id: UUID | None = None  # left out: a new id
    device_a_id: UUID
    device_b_id: UUID
    link_type: LinkType = LinkType.ETHERNET
    label: LinkLabel = None


class ImportFile(RequestModel):
    format: Literal["netscope-export"]
    schema_version: StrictInt
    # Accepted and ignored (exports contain them).
    app_version: Annotated[str | None, Text(64, optional=True)] = None
    exported_at: datetime | None = None
    settings: ImportSettings = Field(default_factory=ImportSettings)
    categories: Annotated[list[ImportCategory], Field(max_length=MAX_IMPORT_CATEGORIES)] = Field(
        default_factory=list
    )
    devices: Annotated[list[ImportDevice], Field(max_length=MAX_IMPORT_DEVICES)] = Field(
        default_factory=list
    )
    links: Annotated[list[ImportLink], Field(max_length=MAX_IMPORT_LINKS)] = Field(
        default_factory=list
    )


# --- Result ------------------------------------------------------------------------------------


class ImportCounts(BaseModel):
    """What the import does (dry run) or did to one kind of record."""

    added: int
    # Merge only: a record with the same name whose values differ.
    updated: int
    # Merge only: a record with the same name and the same values.
    unchanged: int
    # Replace all only: every record NetScope had.
    deleted: int


class ImportResult(BaseModel):
    mode: ImportMode
    dry_run: bool
    categories: ImportCounts
    devices: ImportCounts
    links: ImportCounts
    # Replace all: the file's settings differ from the stored ones. Merge: always false.
    settings_changed: bool
    # The copy of the database made before the import (file name only, next to the
    # database). None on a dry run.
    backup_file: str | None
    # Devices in the file whose status check is on: NetScope checks them right after the
    # import (they start at "Waiting for check").
    checks_on: int
    # The added and the updated devices by name, as the names will be after the import,
    # sorted case-insensitively, at most MAX_LISTED_NAMES each (the counts give the totals).
    # Merge: a device renamed in the file is added, so it shows here. Replace all: every
    # device of the file is added, none updated.
    added_device_names: list[str]
    updated_device_names: list[str]
