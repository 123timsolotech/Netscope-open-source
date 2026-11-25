"""The user's settings: status check interval, timeout, failures before down, history
retention (session required)."""

from dataclasses import asdict

from fastapi import APIRouter

from app.api.deps import Db
from app.schemas.settings import SettingsOut, SettingsUpdate
from app.services import app_settings as settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings(db: Db) -> SettingsOut:
    return SettingsOut(**asdict(settings_service.get_settings(db)))


@router.patch("")
def update_settings(body: SettingsUpdate, db: Db) -> SettingsOut:
    """Partial update. The status monitor uses the new values within a few seconds."""
    return SettingsOut(**asdict(settings_service.update_settings(db, body)))
