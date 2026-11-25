from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUID_LENGTH, Base, uuid_pk

if TYPE_CHECKING:
    from app.models.device import Device


class StatusCheck(Base):
    """One check result. Rolling window, purged in the background (M6)."""

    __tablename__ = "status_checks"
    __table_args__ = (Index("ix_status_checks_device_id_checked_at", "device_id", "checked_at"),)

    id: Mapped[str] = uuid_pk()
    device_id: Mapped[str] = mapped_column(
        String(UUID_LENGTH), ForeignKey("devices.id", ondelete="CASCADE")
    )
    # Own index so the purge job can delete old rows without a full scan.
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    is_up: Mapped[bool] = mapped_column(Boolean(create_constraint=True, name="is_up"))
    latency_ms: Mapped[float | None] = mapped_column(Float)

    device: Mapped["Device"] = relationship(back_populates="status_checks")
