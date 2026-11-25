import enum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUID_LENGTH, Base, str_enum, uuid_pk

if TYPE_CHECKING:
    from app.models.device import Device


class Protocol(enum.StrEnum):
    TCP = "tcp"
    UDP = "udp"


class Service(Base):
    """A port/service running on a device, e.g. 8123/tcp "Home Assistant".

    Port + protocol is unique per device: 53/tcp and 53/udp is fine, two 8080/tcp is not.
    The same port on different devices is fine. The services layer (M3) returns a clear
    validation error; the unique constraint is the database's backstop.
    """

    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("port BETWEEN 1 AND 65535", name="port"),
        # Leads with device_id, so it also serves lookups of a device's services.
        UniqueConstraint("device_id", "port", "protocol"),
    )

    id: Mapped[str] = uuid_pk()
    device_id: Mapped[str] = mapped_column(
        String(UUID_LENGTH), ForeignKey("devices.id", ondelete="CASCADE")
    )
    port: Mapped[int] = mapped_column(Integer)
    protocol: Mapped[Protocol] = mapped_column(str_enum(Protocol, "protocol"), default=Protocol.TCP)
    name: Mapped[str] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(Text)

    device: Mapped["Device"] = relationship(back_populates="services")
