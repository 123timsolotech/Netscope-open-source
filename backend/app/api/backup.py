"""JSON export and import (M8, session required). The logic lives in ``services/backup.py``.

``POST /api/import`` takes the export file's JSON as its body, so the request stays JSON (the
cross-site protection, security audit A.2) and its own size limit applies
(``IMPORT_BODY_LIMIT`` in ``app/api/guards.py``).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Request, Response

from app.api.deps import Db, Oui
from app.core.config import Settings
from app.schemas.backup import ExportFile, ImportMode, ImportResult
from app.services import backup as backup_service

router = APIRouter(tags=["backup"])


@router.get("/export")
def export_data(db: Db, response: Response) -> ExportFile:
    """Everything the user entered, as one JSON file (a download)."""
    data = backup_service.export_data(db)
    day = data.exported_at.strftime("%Y-%m-%d")
    response.headers["Content-Disposition"] = f'attachment; filename="netscope-export-{day}.json"'
    response.headers["Cache-Control"] = "no-store"
    return data


@router.post("/import")
def import_data(
    request: Request,
    db: Db,
    oui: Oui,
    mode: ImportMode = ImportMode.REPLACE,
    dry_run: bool = False,
    # Any JSON (or none): the service's format check answers "This is not a NetScope export
    # file." for anything that is not one, instead of a type error about the body.
    body: Annotated[Any, Body()] = None,
) -> ImportResult:
    """Check an export file completely, then (unless ``dry_run``) write it in one transaction,
    after copying the database. Every problem is a 422 in the usual list format, with ``loc``
    pointing into the file (``["body", "devices", 3, "services", 1, "port"]``); nothing is
    written then."""
    settings: Settings = request.app.state.settings
    return backup_service.import_data(
        db,
        oui,
        body,
        mode=mode,
        dry_run=dry_run,
        database_file=settings.database_file,
    )
