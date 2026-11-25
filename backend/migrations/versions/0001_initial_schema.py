"""Initial schema: the eight tables from brief section 6.

Categories, devices, services, links, status checks, users, sessions and app settings.

Revision ID: 0001
Revises:
Create Date: 2026-11-15 17:08:04.276901

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_app_settings")),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("name_key", sa.String(length=64), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.Column("icon", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("name_key", name=op.f("uq_categories_name_key")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("name_key", sa.String(length=100), nullable=False),
        sa.Column("hostname", sa.String(length=253), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("mac_address", sa.String(length=17), nullable=True),
        sa.Column("vendor", sa.String(length=255), nullable=True),
        sa.Column("category_id", sa.String(length=36), nullable=True),
        sa.Column("role", sa.String(length=100), nullable=True),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("map_x", sa.Float(), nullable=True),
        sa.Column("map_y", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "check_type",
            sa.Enum(
                "none",
                "icmp",
                "tcp",
                "http",
                name="check_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "check_enabled",
            sa.Boolean(create_constraint=True, name="check_enabled"),
            nullable=False,
        ),
        sa.Column("check_port", sa.Integer(), nullable=True),
        sa.Column(
            "check_scheme",
            sa.Enum(
                "http", "https", name="check_scheme", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("check_path", sa.String(length=2048), nullable=False),
        sa.Column(
            "check_verify_tls",
            sa.Boolean(create_constraint=True, name="check_verify_tls"),
            nullable=False,
        ),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column(
            "last_is_up", sa.Boolean(create_constraint=True, name="last_is_up"), nullable=True
        ),
        sa.Column("last_latency_ms", sa.Float(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "check_port IS NULL OR check_port BETWEEN 1 AND 65535",
            name=op.f("ck_devices_check_port"),
        ),
        sa.CheckConstraint(
            "consecutive_failures >= 0", name=op.f("ck_devices_consecutive_failures")
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_devices_category_id_categories"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_devices")),
        sa.UniqueConstraint("name_key", name=op.f("uq_devices_name_key")),
    )
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_devices_category_id"), ["category_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_devices_ip_address"), ["ip_address"], unique=False)

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
    )
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sessions_expires_at"), ["expires_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_sessions_user_id"), ["user_id"], unique=False)

    op.create_table(
        "links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_a_id", sa.String(length=36), nullable=False),
        sa.Column("device_b_id", sa.String(length=36), nullable=False),
        sa.Column(
            "link_type",
            sa.Enum(
                "ethernet",
                "wifi",
                "vpn",
                "other",
                name="link_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.CheckConstraint("device_a_id < device_b_id", name=op.f("ck_links_ordered_device_ids")),
        sa.ForeignKeyConstraint(
            ["device_a_id"],
            ["devices.id"],
            name=op.f("fk_links_device_a_id_devices"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["device_b_id"],
            ["devices.id"],
            name=op.f("fk_links_device_b_id_devices"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_links")),
        sa.UniqueConstraint(
            "device_a_id", "device_b_id", name=op.f("uq_links_device_a_id_device_b_id")
        ),
    )
    with op.batch_alter_table("links", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_links_device_b_id"), ["device_b_id"], unique=False)

    op.create_table(
        "services",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column(
            "protocol",
            sa.Enum("tcp", "udp", name="protocol", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("port BETWEEN 1 AND 65535", name=op.f("ck_services_port")),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_services_device_id_devices"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
        sa.UniqueConstraint(
            "device_id", "port", "protocol", name=op.f("uq_services_device_id_port_protocol")
        ),
    )

    op.create_table(
        "status_checks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.Column("is_up", sa.Boolean(create_constraint=True, name="is_up"), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_status_checks_device_id_devices"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_status_checks")),
    )
    with op.batch_alter_table("status_checks", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_status_checks_checked_at"), ["checked_at"], unique=False
        )
        batch_op.create_index(
            "ix_status_checks_device_id_checked_at", ["device_id", "checked_at"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("status_checks", schema=None) as batch_op:
        batch_op.drop_index("ix_status_checks_device_id_checked_at")
        batch_op.drop_index(batch_op.f("ix_status_checks_checked_at"))

    op.drop_table("status_checks")
    op.drop_table("services")
    with op.batch_alter_table("links", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_links_device_b_id"))

    op.drop_table("links")
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sessions_user_id"))
        batch_op.drop_index(batch_op.f("ix_sessions_expires_at"))

    op.drop_table("sessions")
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_devices_ip_address"))
        batch_op.drop_index(batch_op.f("ix_devices_category_id"))

    op.drop_table("devices")
    op.drop_table("users")
    op.drop_table("categories")
    op.drop_table("app_settings")
