"""JSON export and import (M8). Owner decisions: brief section 4, "Release decisions".

**Export:** every category, device (with its services) and link, and the status-check
settings the user changed. Never the password, sessions, status history or latest status.
All of it is read in one SQLite read transaction: pysqlite starts no transaction for plain
reads (decision M7.2), and a link read after a device was created in between would point at
a device missing from the file, which the import then refuses.

**Import**, in this order:

1. The file is checked completely: the format and version first (a wrong file gets one clear
   message), then its shape (the forms' rules, ``schemas/backup.py``), then the rules between
   its entries (unique ids and names, references inside the file, the device rules). Every
   problem is reported at once; ``loc`` points into the file. Nothing is written then.
2. A dry run answers what the import would do and writes nothing.
3. Otherwise the database is copied next to itself, outside any write transaction: a big
   copy must not hold SQLite's write lock. After a successful import only the newest
   ``IMPORT_BACKUPS_TO_KEEP`` copies are kept (apart from the migration backups); a failed
   import keeps them all.
4. The summary and the writes happen in one ``BEGIN IMMEDIATE`` transaction, so what the
   import reads (merge: the devices with the same names) cannot change before it writes. A
   broken constraint still never gives a 500: it is answered with ``ImportConflictError``.

The status monitor keeps running: its compare-and-set (``services/status.py``) drops results
for devices the import deleted, replaced or whose check it changed.
"""

import logging
import threading
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.exc import StaleDataError

from app import __version__
from app.core.migrate import backup_database, prune_backups
from app.core.timeutil import utcnow
from app.models import AppSetting, Category, CheckType, Device, Link, Service, StatusCheck
from app.models.base import name_key, new_uuid
from app.schemas.backup import (
    EXPORT_FORMAT,
    MAX_IMPORT_CATEGORIES,
    MAX_IMPORT_DEVICES,
    MAX_IMPORT_LINKS,
    MAX_IMPORT_SERVICES,
    MAX_LISTED_NAMES,
    MAX_REPORTED_ISSUES,
    SCHEMA_VERSION,
    ExportCategory,
    ExportDevice,
    ExportFile,
    ExportLink,
    ImportCategory,
    ImportCounts,
    ImportDevice,
    ImportFile,
    ImportLink,
    ImportMode,
    ImportResult,
    ImportSettings,
)
from app.schemas.device import ServiceIn
from app.services import app_settings as settings_service
from app.services import devices as device_service
from app.services import links as link_service
from app.services.app_settings import AppSettings
from app.services.devices import (
    _check_settings,
    _new_service,
    _reset_status,
    _service_keys,
    device_rule_issues,
    free_grid_cells,
    vendor_for_mac,
)
from app.services.errors import InvalidInputError, Issue, ServiceError
from app.services.oui import OuiDatabase
from app.services.status import purge_history

logger = logging.getLogger("netscope.backup")

# Copies of the database made before an import: ``<db>.pre-import-<UTC timestamp>`` next to
# it, the newest 3 kept (separate from the 3 migration backups, ``<db>.bak-...``).
IMPORT_BACKUP_MARKER = ".pre-import-"
IMPORT_BACKUPS_TO_KEEP = 3

# Device columns an import takes from the file as they are (the category is mapped; the
# vendor, position, times and services are handled on their own).
_DEVICE_FIELDS = (
    "name",
    "hostname",
    "ip_address",
    "mac_address",
    "role",
    "location",
    "description",
    "check_type",
    "check_enabled",
    "check_port",
    "check_scheme",
    "check_path",
    "check_verify_tls",
)
_SETTING_KEYS = tuple(f.name for f in fields(AppSettings))


class ImportBusyError(ServiceError):
    """Another import is copying or writing right now (409)."""

    def __init__(self) -> None:
        super().__init__("Another import is running. Try again when it has finished.")


# One real import at a time (NetScope runs one process): two at once would copy, clear and
# write over each other, and the second would wait for SQLite's write lock (found in the M8
# review). Dry runs only read and need no turn.
_import_lock = threading.Lock()


class ImportConflictError(ServiceError):
    """A constraint broke while the import wrote, although the file passed every check:
    something else changed NetScope's data at the same moment (409). Nothing was written."""

    def __init__(self) -> None:
        super().__init__("NetScope's data changed during the import. Check the file again.")


# --- Export ------------------------------------------------------------------------------------


def export_data(db: DbSession) -> ExportFile:
    """Every category, device (with services) and link, and the settings the user changed.

    Sorted (categories and devices by name, services by port and protocol, links by their
    device ids), so the same data always gives the same file apart from ``exported_at``.
    """
    with _read_transaction(db):
        settings = settings_service.stored_values(db)
        categories = db.scalars(select(Category).order_by(Category.name_key)).all()
        devices = device_service.list_devices(db)
        links = link_service.list_links(db)
        # Built inside: the rollback at the end expires every loaded row.
        return ExportFile(
            app_version=__version__,
            exported_at=utcnow(),
            settings=settings,
            categories=[
                ExportCategory(id=c.id, name=c.name, color=c.color, icon=c.icon) for c in categories
            ],
            devices=[ExportDevice.model_validate(d, from_attributes=True) for d in devices],
            links=[ExportLink.model_validate(link, from_attributes=True) for link in links],
        )


# --- Import ------------------------------------------------------------------------------------


@dataclass
class _Counts:
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0

    def out(self) -> ImportCounts:
        return ImportCounts(
            added=self.added, updated=self.updated, unchanged=self.unchanged, deleted=self.deleted
        )

    def __str__(self) -> str:
        return (
            f"{self.added} added, {self.updated} updated, {self.unchanged} unchanged, "
            f"{self.deleted} deleted"
        )


@dataclass
class _Summary:
    categories: _Counts = field(default_factory=_Counts)
    devices: _Counts = field(default_factory=_Counts)
    links: _Counts = field(default_factory=_Counts)
    settings_changed: bool = False
    checks_on: int = 0
    # Device names as they will be after the import.
    added_devices: list[str] = field(default_factory=list)
    updated_devices: list[str] = field(default_factory=list)

    def result(self, mode: ImportMode, *, dry_run: bool, backup_file: str | None) -> ImportResult:
        return ImportResult(
            mode=mode,
            dry_run=dry_run,
            categories=self.categories.out(),
            devices=self.devices.out(),
            links=self.links.out(),
            settings_changed=self.settings_changed,
            backup_file=backup_file,
            checks_on=self.checks_on,
            added_device_names=_listed(self.added_devices),
            updated_device_names=_listed(self.updated_devices),
        )


def _listed(names: list[str]) -> list[str]:
    """Sorted case-insensitively (then exactly, so the order is fixed), the first few."""
    return sorted(names, key=lambda name: (name.casefold(), name))[:MAX_LISTED_NAMES]


def import_data(
    db: DbSession,
    oui: OuiDatabase,
    raw: Any,
    *,
    mode: ImportMode,
    dry_run: bool,
    database_file: Path,
) -> ImportResult:
    """Check the whole file, then (unless ``dry_run``) copy the database and write the file in
    one transaction. Raises InvalidInputError listing every problem; nothing is written then.

    ``db`` must have nothing pending: the import ends the session's transaction before it
    starts its own.
    """
    data = check_file(raw)
    if dry_run:
        with _read_transaction(db):
            summary = _apply(db, oui, data, mode, write=False)
        return summary.result(mode, dry_run=True, backup_file=None)

    if not _import_lock.acquire(blocking=False):
        raise ImportBusyError()
    try:
        return _import(db, oui, raw, data, mode, database_file)
    finally:
        _import_lock.release()


def _import(
    db: DbSession,
    oui: OuiDatabase,
    raw: Any,
    data: ImportFile,
    mode: ImportMode,
    database_file: Path,
) -> ImportResult:
    """The real import, its turn taken: copy, clear the history (replace), write, prune."""
    db.rollback()  # the copy is made outside any transaction of this session
    backup_file = backup_database(database_file, marker=IMPORT_BACKUP_MARKER)
    try:
        if mode == ImportMode.REPLACE:
            _clear_history(db)
        with _write_transaction(db):
            summary = _apply(db, oui, data, mode, write=True)
    except (IntegrityError, StaleDataError):
        # Not reachable through the file (it passed every check) and, inside BEGIN IMMEDIATE,
        # not through other requests either; kept so a missed case is a 409, never a 500.
        _log_failure(mode, backup_file, "on a database constraint")
        check_file(raw)
        raise ImportConflictError() from None
    except Exception:
        _log_failure(mode, backup_file, "", traceback=True)
        raise
    # Only now: a failed import keeps every copy, so retrying a broken import can never push
    # out the copies made before it (found in the M8 review). The next good import prunes.
    _prune_copies(database_file)
    logger.info(
        "Import (%s) done. Categories: %s. Devices: %s. Links: %s. Settings %s. Backup: %s",
        mode,
        summary.categories,
        summary.devices,
        summary.links,
        "replaced" if summary.settings_changed else "unchanged",
        backup_file.name,
    )
    return summary.result(mode, dry_run=False, backup_file=backup_file.name)


def _apply(
    db: DbSession, oui: OuiDatabase, data: ImportFile, mode: ImportMode, *, write: bool
) -> _Summary:
    if mode == ImportMode.REPLACE:
        summary = _replace(db, oui, data, write=write)
    else:
        summary = _merge(db, oui, data, write=write)
    # Every device of the file is added or merged, with the file's check settings.
    summary.checks_on = sum(
        1 for item in data.devices if item.check_enabled and item.check_type != CheckType.NONE
    )
    return summary


# Like the monitor's purge (decision M6.6): short transactions, with a pause in between so
# the monitor and other requests get SQLite's write lock.
HISTORY_BATCH_SIZE = 5_000
HISTORY_BATCH_PAUSE_SECONDS = 0.02


def _clear_history(db: DbSession) -> None:
    """Replace all deletes the status history; this does it first, in batches, outside the
    import's transaction. Inside it, a week of 50 checked devices (1 M rows) held the write
    lock for about 11 s, and the monitor's and other tabs' writes failed meanwhile (found
    while integrating M8). If the import failed after this, the history would be gone (the
    copy made just before still has it); a replace deletes it anyway. The transaction then
    deletes only the few rows the monitor wrote in between."""
    cutoff = utcnow() + timedelta(days=1)
    while purge_history(db, cutoff, HISTORY_BATCH_SIZE) == HISTORY_BATCH_SIZE:
        time.sleep(HISTORY_BATCH_PAUSE_SECONDS)


def _prune_copies(database_file: Path) -> None:
    """Keep the newest copies made before imports (an undo for a wrong file). The migration
    backups (``.bak-``) are neither counted nor touched."""
    for path in prune_backups(database_file, IMPORT_BACKUPS_TO_KEEP, IMPORT_BACKUP_MARKER):
        logger.info("Removed old import backup %s", path.name)


def _log_failure(mode: ImportMode, backup_file: Path, why: str, *, traceback: bool = False) -> None:
    """Name the copy: after a failure it is the way back (a replace may already have cleared
    the status history, which the copy still has)."""
    logger.error(
        "Import (%s) failed%s; the file was not imported. The database as it was before the "
        "import is saved as %s next to it.",
        mode,
        f" {why}" if why else "",
        backup_file.name,
        exc_info=traceback,
    )


# --- Replace all -------------------------------------------------------------------------------


def _replace(db: DbSession, oui: OuiDatabase, data: ImportFile, *, write: bool) -> _Summary:
    """Delete the status history, every service, link, device and category and the stored
    settings, then write the file with its own ids. The admin and the sessions stay.

    Without ``write`` only the summary: what would be added and deleted."""
    summary = _Summary()
    summary.categories.added = len(data.categories)
    summary.devices.added = len(data.devices)
    summary.added_devices = [item.name for item in data.devices]
    summary.links.added = len(data.links)
    summary.settings_changed = _file_settings(data) != settings_service.get_settings(db)
    if not write:
        totals = db.execute(
            select(
                select(func.count()).select_from(Category).scalar_subquery(),
                select(func.count()).select_from(Device).scalar_subquery(),
                select(func.count()).select_from(Link).scalar_subquery(),
            )
        ).one()
        summary.categories.deleted, summary.devices.deleted, summary.links.deleted = totals
        return summary

    # The history (already cleared in batches by _clear_history, except rows the monitor wrote
    # since) and the services first, as whole tables: faster than the cascade from each
    # device.
    _delete_all(db, StatusCheck)
    _delete_all(db, Service)
    # Links before the devices, so their count is not hidden by the cascade.
    summary.links.deleted = _delete_all(db, Link)
    summary.devices.deleted = _delete_all(db, Device)
    summary.categories.deleted = _delete_all(db, Category)
    _delete_all(db, AppSetting)

    now = utcnow()
    for category in data.categories:
        db.add(
            Category(
                id=str(category.id), name=category.name, color=category.color, icon=category.icon
            )
        )
    # Devices without a position get free cells around the file's positions.
    placed = [_position(item) for item in data.devices]
    cells = iter(
        free_grid_cells(
            (position for position in placed if position is not None),
            placed.count(None),
        )
    )
    for item, file_position in zip(data.devices, placed, strict=True):
        position = file_position or next(cells)
        device = Device(
            id=str(item.id),
            **_device_values(item, None if item.category_id is None else str(item.category_id)),
            vendor=vendor_for_mac(oui, item.mac_address),
            map_x=position[0],
            map_y=position[1],
            created_at=_stored_time(item.created_at, now),
            updated_at=_stored_time(item.updated_at, now),
        )
        device.services = [_new_service(service) for service in item.services]
        db.add(device)
    for link in data.links:
        low, high = sorted((str(link.device_a_id), str(link.device_b_id)))
        db.add(
            Link(
                id=new_uuid() if link.id is None else str(link.id),
                device_a_id=low,
                device_b_id=high,
                link_type=link.link_type,
                label=link.label,
            )
        )
    for key, value in _file_setting_values(data).items():
        db.add(AppSetting(key=key, value=str(value)))
    db.flush()
    return summary


def _delete_all(
    db: DbSession,
    model: type[Category | Device | Link | AppSetting | Service | StatusCheck],
) -> int:
    result = db.execute(delete(model).execution_options(synchronize_session=False))
    return int(getattr(result, "rowcount", 0) or 0)


# --- Merge by device name ----------------------------------------------------------------------


def _existing_categories(db: DbSession) -> dict[str, Category]:
    return {category.name_key: category for category in db.scalars(select(Category))}


def _existing_devices(db: DbSession) -> dict[str, Device]:
    devices = db.scalars(select(Device).options(selectinload(Device.services)))
    return {device.name_key: device for device in devices}


def _existing_links(db: DbSession) -> dict[tuple[str, str], Link]:
    return {(link.device_a_id, link.device_b_id): link for link in db.scalars(select(Link))}


def _merge(db: DbSession, oui: OuiDatabase, data: ImportFile, *, write: bool) -> _Summary:
    """The file wins for names NetScope has; nothing is deleted; the settings stay.

    - A category with the same name takes the file's color and icon; others are added with a
      new id.
    - A device with the same name takes every field from the file (its category mapped to the
      category's id here, its services replaced, its position if the file has one, the vendor
      looked up again) and keeps its id and ``created_at``. A changed check resets its status
      (as ``update_device`` does); ``updated_at`` moves only when something other than the
      position changed (moving is not an edit, decisions M3.19 and M7.12). Other devices are
      added with a new id, at the file's position or in a free grid cell.
    - A link between two devices that are already linked takes the file's type and label;
      others are added with a new id.
    """
    summary = _Summary()
    now = utcnow()

    category_ids: dict[UUID, str] = {}
    categories = _existing_categories(db)
    for entry in data.categories:
        category = categories.get(name_key(entry.name))
        if category is None:
            category_ids[entry.id] = new_uuid()
            summary.categories.added += 1
            if write:
                db.add(
                    Category(
                        id=category_ids[entry.id],
                        name=entry.name,
                        color=entry.color,
                        icon=entry.icon,
                    )
                )
            continue
        category_ids[entry.id] = category.id
        if (category.color, category.icon) == (entry.color, entry.icon):
            summary.categories.unchanged += 1
            continue
        summary.categories.updated += 1
        if write:
            category.color, category.icon = entry.color, entry.icon

    device_ids: dict[UUID, str] = {}
    devices = _existing_devices(db)
    # Where the devices will be, for the free grid cells of new devices without a position.
    taken: list[tuple[float, float]] = []
    unplaced: list[Device] = []
    replaced_services: list[tuple[Device, Sequence[ServiceIn]]] = []
    for item in data.devices:
        values = _device_values(
            item, None if item.category_id is None else category_ids[item.category_id]
        )
        position = _position(item)
        device = devices.pop(name_key(item.name), None)
        if device is None:
            device_ids[item.id] = new_uuid()
            summary.devices.added += 1
            summary.added_devices.append(item.name)
            new = Device(
                id=device_ids[item.id],
                **values,
                vendor=vendor_for_mac(oui, item.mac_address),
                created_at=now,
                updated_at=now,
            )
            if position is None:
                unplaced.append(new)
            else:
                new.map_x, new.map_y = position
                taken.append(position)
            if write:
                new.services = [_new_service(service) for service in item.services]
                db.add(new)
            continue

        device_ids[item.id] = device.id
        edited = any(getattr(device, key) != value for key, value in values.items())
        services_changed = _service_keys(item.services) != _service_keys(device.services)
        moved = position is not None and position != (device.map_x, device.map_y)
        if position is not None:
            taken.append(position)
        elif device.map_x is not None and device.map_y is not None:
            taken.append((device.map_x, device.map_y))
        if edited or services_changed or moved:
            summary.devices.updated += 1
            summary.updated_devices.append(item.name)  # merge takes the file's spelling
        else:
            summary.devices.unchanged += 1
        if not write:
            continue
        old_check = _check_settings(device)
        for key, value in values.items():
            setattr(device, key, value)
        device.vendor = vendor_for_mac(oui, device.mac_address)
        if _check_settings(device) != old_check:
            _reset_status(device)
        if position is not None:
            device.map_x, device.map_y = position
        if edited or services_changed:
            device.updated_at = now
        if services_changed:
            # Deleted in a flush before the new rows are added: in one flush SQLAlchemy inserts
            # before it deletes, which would trip the (device, port, protocol) constraint.
            device.services.clear()
            replaced_services.append((device, item.services))

    taken.extend(
        (device.map_x, device.map_y)
        for device in devices.values()  # the devices the file does not name stay where they are
        if device.map_x is not None and device.map_y is not None
    )
    for device, (x, y) in zip(unplaced, free_grid_cells(taken, len(unplaced)), strict=True):
        device.map_x, device.map_y = x, y

    if write:
        db.flush()
        for device, services in replaced_services:
            device.services.extend(_new_service(service) for service in services)

    links = _existing_links(db)
    for file_link in data.links:
        low, high = sorted((device_ids[file_link.device_a_id], device_ids[file_link.device_b_id]))
        link = links.get((low, high))
        if link is None:
            summary.links.added += 1
            if write:
                db.add(
                    Link(
                        id=new_uuid(),
                        device_a_id=low,
                        device_b_id=high,
                        link_type=file_link.link_type,
                        label=file_link.label,
                    )
                )
            continue
        if (link.link_type, link.label) == (file_link.link_type, file_link.label):
            summary.links.unchanged += 1
            continue
        summary.links.updated += 1
        if write:
            link.link_type, link.label = file_link.link_type, file_link.label

    if write:
        db.flush()
    return summary


# --- Helpers -----------------------------------------------------------------------------------


def _position(item: ImportDevice) -> tuple[float, float] | None:
    """The file's map position (the rules make sure it has both coordinates or neither)."""
    if item.map_x is None or item.map_y is None:
        return None
    return item.map_x, item.map_y


def _device_values(item: ImportDevice, category_id: str | None) -> dict[str, Any]:
    values = {key: getattr(item, key) for key in _DEVICE_FIELDS}
    values["category_id"] = category_id
    return values


def _file_setting_values(data: ImportFile) -> dict[str, int]:
    """The settings the file sets (null or left out: the default)."""
    dumped = data.settings.model_dump()
    return {key: dumped[key] for key in _SETTING_KEYS if dumped.get(key) is not None}


def _file_settings(data: ImportFile) -> AppSettings:
    """The settings in effect after a replace: the file's values, defaults for the rest."""
    return AppSettings(**_file_setting_values(data))


def _stored_time(value: datetime | None, default: datetime) -> datetime:
    """A time from the file (already naive UTC: ``ImportTime`` in ``schemas/backup.py``), or
    ``default`` when the file has none."""
    return default if value is None else value


@contextmanager
def _read_transaction(db: DbSession) -> Iterator[None]:
    """Run the reads inside on one snapshot of the database (an SQLite read transaction;
    pysqlite starts none for plain reads, decision M7.2). Ends with a rollback, which also
    expires every loaded row."""
    db.rollback()
    db.execute(text("BEGIN"))
    try:
        yield
    finally:
        db.rollback()


@contextmanager
def _write_transaction(db: DbSession) -> Iterator[None]:
    """One write transaction that holds SQLite's write lock from the start (``BEGIN
    IMMEDIATE``; it waits for another writer up to the busy timeout), so nothing else can
    write between what the import reads and what it writes. Commits once at the end; any
    error rolls everything back."""
    db.rollback()
    db.execute(text("BEGIN IMMEDIATE"))
    try:
        yield
        db.commit()
    except BaseException:
        db.rollback()
        raise


# --- Checking the file -------------------------------------------------------------------------


def check_file(raw: Any) -> ImportFile:
    """The file, validated: format and version, sizes, shape, and the rules between its
    entries. Raises InvalidInputError with the problems (``loc`` inside the file; at most
    ``MAX_REPORTED_ISSUES`` of them, plus one item saying how many more there are)."""
    _check_format(raw)
    _check_sizes(raw)
    data = _validated(raw)
    issues = file_rule_issues(data)
    if issues:
        raise InvalidInputError(_capped(issues))
    return data


# Entry lists of the file and the model of one entry.
_ENTRY_MODELS: dict[str, type[ImportCategory | ImportDevice | ImportLink]] = {
    "categories": ImportCategory,
    "devices": ImportDevice,
    "links": ImportLink,
}


class _Problems:
    """Collects the first ``MAX_REPORTED_ISSUES`` validation problems and counts the rest
    without building them (``ValidationError.errors()`` builds every one: 160 MB for the
    165,000 problems a 1.4 MB file can have, found in the M8 review)."""

    def __init__(self) -> None:
        self.issues: list[Issue] = []
        self.more = 0

    def add(self, error: ValidationError, prefix: tuple[str | int, ...] = ()) -> None:
        room = MAX_REPORTED_ISSUES - len(self.issues)
        if room <= 0:
            self.more += error.error_count()
            return
        # Never the input value: a file can hold anything.
        items = error.errors(include_url=False, include_input=False)
        self.issues.extend(
            Issue((*prefix, *item["loc"]), item["msg"], item["type"]) for item in items[:room]
        )
        self.more += max(0, len(items) - room)


def _validated(raw: dict[str, Any]) -> ImportFile:
    """``ImportFile.model_validate(raw)``, one entry at a time: each entry's problems are
    built only while there is room in the answer, so memory stays small however many
    problems the file has."""
    entries = {key: raw[key] for key in _ENTRY_MODELS if isinstance(raw.get(key), list)}
    problems = _Problems()
    shell: ImportFile | None = None
    try:  # everything but the entries (a list that is not a list is reported here)
        shell = ImportFile.model_validate({**raw, **dict.fromkeys(entries, [])})
    except ValidationError as error:
        problems.add(error)
    validated: dict[str, list[Any]] = {}
    for key, items in entries.items():
        model = _ENTRY_MODELS[key]
        validated[key] = []
        for index, item in enumerate(items):
            try:
                validated[key].append(model.model_validate(item))
            except ValidationError as error:
                problems.add(error, (key, index))
    if problems.issues or shell is None:  # the shell's own problems come first
        raise InvalidInputError(_capped(problems.issues, more=problems.more))
    return shell.model_copy(update=validated)


def _check_sizes(raw: dict[str, Any]) -> None:
    """Too many entries, services or unknown fields: one issue for each, before anything else
    is checked, so a small file cannot make the checks build hundreds of thousands of
    problems (found in the M8 review). Counted on the raw JSON; the schema checks the
    entries themselves."""
    issues: list[Issue] = []
    for key, limit in (
        ("categories", MAX_IMPORT_CATEGORIES),
        ("devices", MAX_IMPORT_DEVICES),
        ("links", MAX_IMPORT_LINKS),
    ):
        entries = raw.get(key)
        if isinstance(entries, list) and len(entries) > limit:
            issues.append(
                Issue(
                    (key,),
                    f"The file has {len(entries):,} {key}; NetScope imports at most {limit:,}.",
                    "too_long",
                )
            )
    devices = raw.get("devices")
    if isinstance(devices, list):
        services = sum(
            len(device["services"])
            for device in devices
            if isinstance(device, dict) and isinstance(device.get("services"), list)
        )
        if services > MAX_IMPORT_SERVICES:
            issues.append(
                Issue(
                    ("devices",),
                    f"The devices in the file have {services:,} services in all; NetScope "
                    f"imports at most {MAX_IMPORT_SERVICES:,}.",
                    "too_many_services",
                )
            )
    unknown = list(_unknown_fields(raw))
    if len(unknown) > MAX_REPORTED_ISSUES:
        issues.append(
            Issue(
                unknown[0],
                f"NetScope does not know this field, nor {len(unknown) - 1:,} other fields in "
                "the file.",
                "too_many_unknown_fields",
            )
        )
    if issues:
        raise InvalidInputError(issues)


def _unknown_fields(raw: dict[str, Any]) -> Iterator[tuple[str | int, ...]]:
    """Where the file has fields the import does not know (the schema rejects each one; a
    file of nothing but unknown fields would otherwise give a problem per field)."""

    def unknown(value: Any, model: type[BaseModel], loc: tuple[str | int, ...]) -> Iterator[Any]:
        if isinstance(value, dict):
            yield from ((*loc, key) for key in value if key not in model.model_fields)

    yield from unknown(raw, ImportFile, ())
    yield from unknown(raw.get("settings"), ImportSettings, ("settings",))
    for key, model in _ENTRY_MODELS.items():
        entries = raw.get(key)
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            yield from unknown(entry, model, (key, index))
            services = (
                entry.get("services") if key == "devices" and isinstance(entry, dict) else None
            )
            if isinstance(services, list):
                for number, service in enumerate(services):
                    yield from unknown(service, ServiceIn, (key, index, "services", number))


def _capped(issues: list[Issue], more: int = 0) -> list[Issue]:
    """The first ``MAX_REPORTED_ISSUES`` problems, and one more saying how many are left out
    (``loc`` is the body itself)."""
    more += max(0, len(issues) - MAX_REPORTED_ISSUES)
    if not more:
        return issues
    return [
        *issues[:MAX_REPORTED_ISSUES],
        Issue((), f"…and {more:,} more problems.", "too_many_problems"),
    ]


def _check_format(raw: Any) -> None:
    """One clear message for a file that is not an export (also any JSON that is not an
    object, or no body at all), or of a version this NetScope cannot read, instead of a page
    of field errors."""
    if not isinstance(raw, dict) or raw.get("format") != EXPORT_FORMAT:
        raise InvalidInputError(
            Issue(("format",), "This is not a NetScope export file.", "not_an_export")
        )
    version = raw.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise InvalidInputError(
            Issue(
                ("schema_version",),
                "The file's format version is missing or not a whole number.",
                "invalid_schema_version",
            )
        )
    if version > SCHEMA_VERSION:
        raise InvalidInputError(
            Issue(
                ("schema_version",),
                f"This file was made by a newer version of NetScope (format version "
                f"{version}). Update NetScope, then import it again.",
                "newer_schema",
            )
        )
    if version < 1:
        raise InvalidInputError(
            Issue(
                ("schema_version",),
                f"Unknown format version {version}.",
                "invalid_schema_version",
            )
        )


def file_rule_issues(data: ImportFile) -> list[Issue]:
    """The rules between the file's entries, all of them at once: unique ids and names (names
    compared as the database does, ``name_key``), references inside the file, the device
    API's check and service rules, complete positions, links, and the settings pair."""
    issues: list[Issue] = []

    category_ids: dict[UUID, str] = {}
    category_names: dict[str, str] = {}
    for index, category in enumerate(data.categories):
        loc = ("categories", index)
        if category.id in category_ids:
            issues.append(
                Issue(
                    (*loc, "id"),
                    f'The category "{category_ids[category.id]}" in the file has the same id.',
                    "duplicate_id",
                )
            )
        else:
            category_ids[category.id] = category.name
        key = name_key(category.name)
        if key in category_names:
            issues.append(
                Issue(
                    (*loc, "name"),
                    f'Another category in the file is also named "{category_names[key]}".',
                    "duplicate_name",
                )
            )
        else:
            category_names[key] = category.name

    device_ids: dict[UUID, str] = {}
    device_names: dict[str, str] = {}
    for index, device in enumerate(data.devices):
        loc = ("devices", index)
        if device.id in device_ids:
            issues.append(
                Issue(
                    (*loc, "id"),
                    f'The device "{device_ids[device.id]}" in the file has the same id.',
                    "duplicate_id",
                )
            )
        else:
            device_ids[device.id] = device.name
        key = name_key(device.name)
        if key in device_names:
            issues.append(
                Issue(
                    (*loc, "name"),
                    f'Another device in the file is also named "{device_names[key]}".',
                    "duplicate_name",
                )
            )
        else:
            device_names[key] = device.name
        if device.category_id is not None and device.category_id not in category_ids:
            issues.append(
                Issue(
                    (*loc, "category_id"),
                    "This category is not in the file.",
                    "category_not_found",
                )
            )
        values = {key: getattr(device, key) for key in _DEVICE_FIELDS}
        issues.extend(
            Issue((*loc, *issue.loc), issue.msg, issue.type)
            for issue in device_rule_issues(values, device.services)
        )
        if (device.map_x is None) != (device.map_y is None):
            missing = "map_x" if device.map_x is None else "map_y"
            issues.append(
                Issue(
                    (*loc, missing),
                    "A map position needs both map_x and map_y.",
                    "position_incomplete",
                )
            )

    link_ids: set[UUID] = set()
    pairs: set[frozenset[UUID]] = set()
    for index, link in enumerate(data.links):
        loc = ("links", index)
        if link.id is not None:
            if link.id in link_ids:
                issues.append(
                    Issue((*loc, "id"), "Another link in the file has the same id.", "duplicate_id")
                )
            link_ids.add(link.id)
        found = True
        for key, device_id in (
            ("device_a_id", link.device_a_id),
            ("device_b_id", link.device_b_id),
        ):
            if device_id not in device_ids:
                found = False
                issues.append(
                    Issue((*loc, key), "This device is not in the file.", "device_not_found")
                )
        if link.device_a_id == link.device_b_id:
            issues.append(
                Issue((*loc, "device_b_id"), "A device cannot be linked to itself.", "self_link")
            )
        elif found:
            pair = frozenset((link.device_a_id, link.device_b_id))
            if pair in pairs:
                a, b = device_ids[link.device_a_id], device_ids[link.device_b_id]
                issues.append(
                    Issue(
                        (*loc, "device_b_id"),
                        f'Another link in the file also joins "{a}" and "{b}".',
                        "duplicate_link",
                    )
                )
            pairs.add(pair)

    settings = _file_settings(data)
    if not settings_service.timeout_fits(
        settings.check_interval_seconds, settings.check_timeout_seconds
    ):
        issue = settings_service.timeout_too_long(settings.check_interval_seconds)
        issues.append(Issue(("settings", *issue.loc), issue.msg, issue.type))
    return issues
