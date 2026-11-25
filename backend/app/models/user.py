from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utc_timestamp, uuid_pk


class User(Base):
    """The single admin account (brief section 7)."""

    __tablename__ = "users"

    id: Mapped[str] = uuid_pk()
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))  # argon2 (M2)
    created_at: Mapped[datetime] = utc_timestamp()
