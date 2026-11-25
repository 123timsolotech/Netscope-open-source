"""Default categories (owner decision, M3): created once on a new database.

Data only, no schema change. Names that already exist (in any letter case) are skipped, so
this never duplicates or overwrites. Alembic runs it once per database: categories the user
deletes later are not re-created. ``netscope seed`` adds missing defaults on request.

Databases from M1/M2 get the defaults too when they upgrade; they cannot have categories
yet (there was no API to create them).

The list is a frozen copy of ``app/services/seed_data.py`` as of M3, and the migration imports
no app code: a migration is history and must keep doing exactly this, whatever later
refactors change (decision M3.12). Changing the defaults later needs a new migration.

Each row is one ``INSERT ... SELECT ... WHERE NOT EXISTS``, so the migration also works in
Alembic's offline mode (``alembic upgrade head --sql``).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-15 21:00:00.000000

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (name, Lucide icon, color)
DEFAULT_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("Router", "router", "#60a5fa"),
    ("Switch", "network", "#818cf8"),
    ("Server", "server", "#a78bfa"),
    ("NAS", "hard-drive", "#c084fc"),
    ("Access point", "wifi", "#5eead4"),
    ("PC", "monitor", "#7dd3fc"),
    ("Phone", "smartphone", "#f472b6"),
    ("IoT", "cpu", "#bef264"),
    ("Printer", "printer", "#e879f9"),
    ("Camera", "cctv", "#fdba74"),
    ("TV / Media", "tv", "#f0abfc"),
    ("Other", "shapes", "#94a3b8"),
)

# Only the columns this migration writes, as they are at this revision.
categories = sa.table(
    "categories",
    sa.column("id", sa.String),
    sa.column("name", sa.String),
    sa.column("name_key", sa.String),
    sa.column("color", sa.String),
    sa.column("icon", sa.String),
)


def upgrade() -> None:
    """Insert each default category whose name is not taken yet."""
    for name, icon, color in DEFAULT_CATEGORIES:
        key = name.strip().casefold()  # same rule as app.models.base.name_key
        row = sa.select(
            sa.literal(str(uuid.uuid4())),
            sa.literal(name),
            sa.literal(key),
            sa.literal(color),
            sa.literal(icon),
        ).where(~sa.exists().where(categories.c.name_key == key))
        op.execute(
            categories.insert().from_select(["id", "name", "name_key", "color", "icon"], row)
        )


def downgrade() -> None:
    """Nothing to undo: the categories are ordinary data now and may have been edited."""
