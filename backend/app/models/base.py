"""Declarative base and shared column helpers."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.timeutil import utcnow

# Fixed constraint names. Alembic's batch mode (needed for SQLite) can only alter
# constraints that have names.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

UUID_LENGTH = 36


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def new_uuid() -> str:
    return str(uuid.uuid4())


def uuid_pk() -> Mapped[str]:
    """UUID primary key stored as a string (brief section 6)."""
    return mapped_column(String(UUID_LENGTH), primary_key=True, default=new_uuid)


def utc_timestamp() -> Mapped[datetime]:
    """Naive UTC timestamp, set on insert. Never changed automatically on update."""
    return mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=utcnow,
    )


def str_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    """Store a StrEnum by value as VARCHAR with a CHECK constraint."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=max(len(member.value) for member in enum_cls),
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


# Invisible characters that request text keeps (emoji and some scripts need them) but that
# must not make two names different: "nas" and "nas" + U+200D are the same name. ZWNJ/ZWJ,
# variation selectors, emoji tag characters, Mongolian variation selectors.
_NAME_KEY_IGNORED = frozenset(
    chr(code)
    for first, last in (
        (0x200C, 0x200D),
        (0xFE00, 0xFE0F),
        (0xE0100, 0xE01EF),
        (0xE0020, 0xE007F),
        (0x180B, 0x180D),
        (0x180F, 0x180F),
    )
    for code in range(first, last + 1)
)


def name_key(name: str) -> str:
    """Case-insensitive key used for unique names (Unicode-aware, unlike SQLite NOCASE).

    Ignores joiners and variation selectors (decision M3.20). Request text has already been
    cleaned by ``schemas.common.Text`` (other invisible characters removed, spaces collapsed).
    """
    return "".join(ch for ch in name.strip().casefold() if ch not in _NAME_KEY_IGNORED)
