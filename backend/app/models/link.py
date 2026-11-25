import enum

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUID_LENGTH, Base, str_enum, uuid_pk
from app.models.device import Device


class LinkType(enum.StrEnum):
    ETHERNET = "ethernet"
    WIFI = "wifi"
    VPN = "vpn"
    OTHER = "other"


class Link(Base):
    """Undirected link between two devices.

    Stored with ``device_a_id < device_b_id`` (brief section 6), so A-B and B-A are the
    same row. The CHECK constraint also rules out self-links; the unique constraint rules
    out duplicates. The services layer (M3) orders the ids before writing.
    """

    __tablename__ = "links"
    __table_args__ = (
        CheckConstraint("device_a_id < device_b_id", name="ordered_device_ids"),
        UniqueConstraint("device_a_id", "device_b_id"),
    )

    id: Mapped[str] = uuid_pk()
    device_a_id: Mapped[str] = mapped_column(
        String(UUID_LENGTH), ForeignKey("devices.id", ondelete="CASCADE")
    )
    device_b_id: Mapped[str] = mapped_column(
        String(UUID_LENGTH), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    link_type: Mapped[LinkType] = mapped_column(
        str_enum(LinkType, "link_type"), default=LinkType.ETHERNET
    )
    label: Mapped[str | None] = mapped_column(String(100))

    device_a: Mapped[Device] = relationship(foreign_keys=[device_a_id])
    device_b: Mapped[Device] = relationship(foreign_keys=[device_b_id])
