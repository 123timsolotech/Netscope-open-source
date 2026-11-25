from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUID_LENGTH, Base, utc_timestamp

TOKEN_HASH_LENGTH = 64  # SHA-256, hex


class Session(Base):
    """Server-side login session (brief section 7). Token handling arrives in M2.

    ``id`` is the SHA-256 hash (hex) of the random session token. The token itself only
    exists in the user's cookie, so a copy of the database cannot be used to log in.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(TOKEN_HASH_LENGTH), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(UUID_LENGTH), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = utc_timestamp()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
