"""Startup settings, read from environment variables (prefix ``NETSCOPE_``) or a ``.env`` file.

Only settings needed before the app can start live here. Everything the user changes in the
UI is stored in the ``app_settings`` table instead (brief section 6).
"""

import ipaddress
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
_HOST_NAME = re.compile(r"[a-z0-9_-]+(\.[a-z0-9_-]+)*")
ENV_PREFIX = "NETSCOPE_"

logger = logging.getLogger("netscope.config")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NETSCOPE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Path of the SQLite database file. Relative paths are resolved against the working
    # directory, so running from backend/ puts the dev database in backend/data/.
    database_path: Path = Path("data/netscope.db")

    # Address used by `python -m app`. Docker (M8) sets host to 0.0.0.0.
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)

    # Folder with the built frontend (index.html + assets). If it does not exist,
    # only the API is served.
    frontend_dist: Path = Path("../frontend/dist")

    log_level: LogLevel = "INFO"

    # First-run setup (brief section 7). If no admin exists at startup:
    # - admin_password set: the admin account is created from admin_username/admin_password;
    # - else the setup page needs a one-time token: setup_token if set, else a random one
    #   printed to the logs.
    setup_token: SecretStr | None = None
    admin_username: str = "admin"
    admin_password: SecretStr | None = None

    # Proxies whose X-Forwarded-For / X-Forwarded-Proto headers are trusted by
    # `python -m app`: comma-separated IP addresses or networks (CIDR). Needed for the Secure
    # cookie behind Tailscale Serve. The Docker setup is documented at M8. "*" is refused: it
    # would let any client fake its address (bypassing the login limit) and HTTPS.
    trusted_proxies: str = "127.0.0.1"

    # Extra host names NetScope answers to, comma-separated (owner decision, M2 security
    # audit): exact names ("thinkpad.fritz.box") or ".suffix" entries (".example.org").
    # IP addresses, localhost, single-label names and .local / .home.arpa / .internal /
    # .ts.net names always work; anything else gets 400 (protects against DNS rebinding).
    allowed_hosts: str = ""

    @field_validator("setup_token", "admin_password", mode="before")
    @classmethod
    def _empty_means_unset(cls, value: object) -> object:
        """``NETSCOPE_ADMIN_PASSWORD=`` (empty, as compose files often pass it) means unset."""
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        if isinstance(raw, str) and not raw.strip():
            return None
        return value

    @field_validator("trusted_proxies")
    @classmethod
    def _proxy_addresses(cls, value: str) -> str:
        entries = [entry.strip() for entry in value.split(",") if entry.strip()]
        if not entries:
            raise ValueError("NETSCOPE_TRUSTED_PROXIES needs at least one address.")
        for entry in entries:
            try:
                # As strict as uvicorn: it silently ignores "172.17.0.1/16" (host bits set),
                # which would trust nothing. Networks must be written "172.17.0.0/16".
                if "/" in entry:
                    ipaddress.ip_network(entry)
                else:
                    ipaddress.ip_address(entry)
            except ValueError:
                raise ValueError(
                    f"NETSCOPE_TRUSTED_PROXIES: {entry!r} is not an IP address or a network "
                    "such as 172.17.0.0/16. "
                    'List only your reverse proxy\'s address (not "*": any client could '
                    "then fake its address and HTTPS)."
                ) from None
        return ",".join(entries)

    @field_validator("allowed_hosts")
    @classmethod
    def _host_names(cls, value: str) -> str:
        entries = [entry.strip().lower().rstrip(".") for entry in value.split(",")]
        entries = [entry for entry in entries if entry]
        for entry in entries:
            name = entry.removeprefix(".")
            if not name or "*" in entry or not _HOST_NAME.fullmatch(name):
                raise ValueError(
                    f"NETSCOPE_ALLOWED_HOSTS: {entry!r} is not a host name. Use names such as "
                    "thinkpad.fritz.box, or .example.org for every name under it (no *)."
                )
        return ",".join(entries)

    @property
    def allowed_host_list(self) -> list[str]:
        return [entry for entry in self.allowed_hosts.split(",") if entry]

    @property
    def database_file(self) -> Path:
        """Absolute path of the database file."""
        return self.database_path.expanduser().resolve()


def unknown_environment_variables(environ: dict[str, str] | None = None) -> list[str]:
    """NETSCOPE_* variables that are not settings (usually typos, silently ignored otherwise)."""
    known = {ENV_PREFIX + name.upper() for name in Settings.model_fields}
    names = (environ if environ is not None else os.environ).keys()
    return sorted(
        name for name in names if name.upper().startswith(ENV_PREFIX) and name.upper() not in known
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
