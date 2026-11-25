"""SQLAlchemy models. Importing this package registers every table on ``Base.metadata``."""

from app.models.app_setting import AppSetting
from app.models.base import Base
from app.models.category import Category
from app.models.device import CheckScheme, CheckType, Device, DeviceStatus
from app.models.link import Link, LinkType
from app.models.service import Protocol, Service
from app.models.session import Session
from app.models.status_check import StatusCheck
from app.models.user import User

__all__ = [
    "AppSetting",
    "Base",
    "Category",
    "CheckScheme",
    "CheckType",
    "Device",
    "DeviceStatus",
    "Link",
    "LinkType",
    "Protocol",
    "Service",
    "Session",
    "StatusCheck",
    "User",
]
