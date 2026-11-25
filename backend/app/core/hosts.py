"""Host name allowlist against DNS rebinding (owner decision, M2 security audit).

A website the admin visits can point its own domain name at NetScope's address; the browser
then treats NetScope as part of that website and lets its scripts send requests (without
NetScope's cookie). Answering only to host names NetScope can actually be reached under stops
that. Allowed without configuration:

- IP addresses and ``localhost``,
- single-label names (``thinkpad``): public DNS cannot answer them,
- local-only domains: ``.local``, ``.home.arpa``, ``.internal``, ``.localhost``, and
  ``.ts.net`` (Tailscale controls those answers).

Anything else (``thinkpad.fritz.box``, an own domain) must be listed in
``NETSCOPE_ALLOWED_HOSTS``. Public suffixes such as ``.box`` are never allowed by default:
anyone can register ``evil.box``. Requests without a Host header (HTTP/1.0 scripts) pass:
browsers always send one.
"""

import ipaddress
import json
from collections.abc import Iterable

from starlette.status import HTTP_400_BAD_REQUEST
from starlette.types import ASGIApp, Receive, Scope, Send

LOCAL_SUFFIXES = (".local", ".home.arpa", ".internal", ".localhost", ".ts.net")
NOT_ALLOWED = (
    "NetScope does not answer to this host name. To allow it, add it to "
    "NETSCOPE_ALLOWED_HOSTS and start NetScope again (Docker: docker compose up -d)."
)


def host_name(raw: str) -> str:
    """The name part of a Host header, lower case, without port or trailing dot."""
    host = raw.strip().lower()
    if host.startswith("["):  # IPv6 literal, "[::1]:8000"
        end = host.find("]")
        return host[1:end] if end != -1 else host
    if host.count(":") == 1:  # "name:port"; more colons: a bare IPv6 address
        host = host.rsplit(":", 1)[0]
    return host.rstrip(".")


def host_allowed(name: str, extra: Iterable[str] = ()) -> bool:
    """Whether NetScope answers to ``name``. ``extra``: names, or ``.suffix`` entries."""
    if not name:
        return False
    try:
        ipaddress.ip_address(name.split("%", 1)[0])  # zone ids: "fe80::1%eth0"
        return True
    except ValueError:
        pass
    if name == "localhost" or "." not in name or name.endswith(LOCAL_SUFFIXES):
        return True
    return any(name == entry or (entry.startswith(".") and name.endswith(entry)) for entry in extra)


class HostAllowlistMiddleware:
    """Pure ASGI middleware: 400 for requests to a host name NetScope does not use."""

    def __init__(self, app: ASGIApp, extra_hosts: Iterable[str] = ()) -> None:
        self.app = app
        self.extra_hosts = tuple(extra_hosts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            hosts = [value for name, value in scope["headers"] if name == b"host"]
            if hosts and (
                len(hosts) > 1
                or not host_allowed(host_name(hosts[0].decode("latin-1")), self.extra_hosts)
            ):
                body = json.dumps({"detail": NOT_ALLOWED}).encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": HTTP_400_BAD_REQUEST,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode()),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)
