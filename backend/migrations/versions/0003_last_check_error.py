"""Why the latest status check failed (owner decision, M6).

A nullable text column on devices next to the other cached status columns. Existing devices
get NULL, which is what a device without a failed check has.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-17 19:04:10.241800

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("last_check_error", sa.String(length=200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.drop_column("last_check_error")
