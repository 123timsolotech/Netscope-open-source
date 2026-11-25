import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base import UUID_LENGTH, Base, name_key, str_enum, utc_timestamp, uuid_pk

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.service import Service
    from app.models.status_check import StatusCheck


LAST_CHECK_ERROR_LENGTH = 200


class CheckType(enum.StrEnum):
    NONE = "none"
    ICMP = "icmp"
    TCP = "tcp"
    HTTP = "http"


class DeviceStatus(enum.StrEnum):
    """What the status dot shows (owner decision, M6). Not a column: computed from the cached
    status and the settings by ``services.status.status_of``."""

    OFF = "off"  # check turned off, or no check type
    WAITING = "waiting"  # on, no verdict yet (new or changed check, or one failure so far)
    UP = "up"
    DOWN = "down"  # N failed checks in a row (failures_before_down)
    STALE = "stale"  # the latest result is too old: "No recent check"


class CheckScheme(enum.StrEnum):
    HTTP = "http"
    HTTPS = "https"


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint("check_port IS NULL OR check_port BETWEEN 1 AND 65535", name="check_port"),
        CheckConstraint("consecutive_failures >= 0", name="consecutive_failures"),
    )

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(100))
    # casefold(name); unique, so names are unique case-insensitively.
    name_key: Mapped[str] = mapped_column(String(100), unique=True)
    hostname: Mapped[str | None] = mapped_column(String(253))
    ip_address: Mapped[str | None] = mapped_column(String(45), index=True)
    mac_address: Mapped[str | None] = mapped_column(String(17))  # "AA:BB:CC:DD:EE:FF"
    vendor: Mapped[str | None] = mapped_column(String(255))
    category_id: Mapped[str | None] = mapped_column(
        String(UUID_LENGTH), ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    role: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    map_x: Mapped[float | None] = mapped_column(Float)
    map_y: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = utc_timestamp()
    # Last edit by the user. Set by the services layer, not on every UPDATE: status results
    # (M6) and map moves (M5) must not count as edits (decision M3.19).
    updated_at: Mapped[datetime] = utc_timestamp()

    # Check settings
    check_type: Mapped[CheckType] = mapped_column(
        str_enum(CheckType, "check_type"), default=CheckType.NONE
    )
    check_enabled: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="check_enabled"), default=False
    )
    check_port: Mapped[int | None] = mapped_column(Integer)
    check_scheme: Mapped[CheckScheme] = mapped_column(
        str_enum(CheckScheme, "check_scheme"), default=CheckScheme.HTTP
    )
    check_path: Mapped[str] = mapped_column(String(2048), default="/")
    check_verify_tls: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="check_verify_tls"), default=False
    )

    # Latest status, cached on the device
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_is_up: Mapped[bool | None] = mapped_column(
        Boolean(create_constraint=True, name="last_is_up")
    )
    last_latency_ms: Mapped[float | None] = mapped_column(Float)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    # Why the latest check failed ("Timed out after 5 s", "HTTP 503"); None after a success
    # (owner decision, M6).
    last_check_error: Mapped[str | None] = mapped_column(String(LAST_CHECK_ERROR_LENGTH))

    category: Mapped["Category | None"] = relationship(back_populates="devices")
    services: Mapped[list["Service"]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="[Service.port, Service.protocol]",
    )
    status_checks: Mapped[list["StatusCheck"]] = relationship(
        back_populates="device", cascade="all, delete-orphan", passive_deletes=True
    )

    @validates("name")
    def _sync_name_key(self, _key: str, value: str) -> str:
        self.name_key = name_key(value)
        return value
