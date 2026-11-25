from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base import Base, name_key, uuid_pk

if TYPE_CHECKING:
    from app.models.device import Device


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(64))
    # casefold(name); unique, so names are unique case-insensitively.
    name_key: Mapped[str] = mapped_column(String(64), unique=True)
    color: Mapped[str] = mapped_column(String(7))  # "#RRGGBB"
    icon: Mapped[str] = mapped_column(String(64))  # Lucide icon name

    devices: Mapped[list["Device"]] = relationship(back_populates="category", passive_deletes=True)

    @validates("name")
    def _sync_name_key(self, _key: str, value: str) -> str:
        self.name_key = name_key(value)
        return value
