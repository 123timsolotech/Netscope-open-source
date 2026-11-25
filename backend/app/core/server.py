"""How NetScope's web server treats connections (final security audit, M8).

uvicorn keeps a connection open for as long as the client likes until a complete request has
arrived, and takes as many connections as the operating system allows. One device on the LAN
that opened about 1,100 idle connections used up the container's 1,024 open files (Docker's
default soft limit on the ThinkPad): NetScope stopped answering, every status check failed
("Too many open files") and the log grew by megabytes a second. So ``python -m app``:

1. **Raises the soft limit on open files** to the hard limit (at most ``OPEN_FILES_TARGET``),
   as servers usually do: 524,288 is Docker's hard limit there.
2. **Closes a connection whose request head does not arrive in time**
   (``HEAD_TIMEOUT_SECONDS``, counted from the moment it opened or its previous answer was
   sent). Bodies keep their own limit (30 s, ``app/api/guards.py``).
3. **Caps open connections:** at most ``MAX_CONNECTIONS_PER_ADDRESS`` from one address and
   ``max_connections`` in all; more are closed at once (one warning a minute in the log).
   Addresses in ``NETSCOPE_TRUSTED_PROXIES`` have no per-address cap: every request through
   Tailscale Serve comes from the Docker gateway. The total stays low because a client that
   stops reading its answer keeps the connection and the buffered answer (about 250 KB each in
   the review: 1,024 of them about 250 MB, 64 from one address about 16 MB). A device that uses
   many addresses can still fill the total (accepted: such a device can disturb the LAN
   anyway). There is no timeout for a client that stops reading: telling a stopped one from a
   slow phone needs the kernel's send queue as well (decision in the final audit).

WebSocket upgrades are off (``uvicorn.run(ws="none")``: NetScope has none, and an upgraded
connection would leave this protocol behind). The development server (``uvicorn app.main:app
--reload``) runs without any of this.
"""

import asyncio
import ipaddress
import logging
import sys
import time
from typing import ClassVar

from uvicorn.protocols.http.h11_impl import H11Protocol

from app.core.ratelimit import address_key

logger = logging.getLogger("netscope.server")

HEAD_TIMEOUT_SECONDS = 10.0
MAX_CONNECTIONS_PER_ADDRESS = 64
# Far beyond a home network (each browser opens up to 6), small enough that clients which
# stop reading cannot hold much memory (about 250 KB each in the review: 1,024 x 250 KB).
MAX_CONNECTIONS = 1024
# Open files kept free for the database, the status checks (50 at once) and the log.
RESERVED_FILES = 512
OPEN_FILES_TARGET = 65536
REFUSAL_LOG_INTERVAL_SECONDS = 60.0

IpNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def raise_open_file_limit(target: int = OPEN_FILES_TARGET) -> int | None:
    """Raise the soft limit on open files to the hard limit, at most ``target``. Returns the
    soft limit in effect (None without a limit, and on Windows, which has no such limit)."""
    if sys.platform == "win32":
        return None
    import resource

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    wanted = target if hard == resource.RLIM_INFINITY else min(target, hard)
    if soft == resource.RLIM_INFINITY:
        return None  # no limit at all
    if soft >= wanted:
        return soft
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (wanted, hard))
    except (ValueError, OSError) as error:
        logger.warning("Could not raise the open-file limit from %d: %s", soft, error)
        return soft
    return wanted


def connection_limit(open_files: int | None) -> int:
    """Connections allowed in all: ``MAX_CONNECTIONS``, fewer if open files are scarce."""
    if open_files is None:
        return MAX_CONNECTIONS
    return max(MAX_CONNECTIONS_PER_ADDRESS, min(MAX_CONNECTIONS, open_files - RESERVED_FILES))


def trusted_networks(trusted_proxies: str) -> tuple[IpNetwork, ...]:
    """``NETSCOPE_TRUSTED_PROXIES`` (already checked by the settings) as networks."""
    return tuple(
        ipaddress.ip_network(entry.strip(), strict=False)
        for entry in trusted_proxies.split(",")
        if entry.strip()
    )


class GuardedH11Protocol(H11Protocol):
    """uvicorn's HTTP/1.1 protocol with the head timeout and the connection caps."""

    head_timeout: ClassVar[float] = HEAD_TIMEOUT_SECONDS
    max_per_address: ClassVar[int] = MAX_CONNECTIONS_PER_ADDRESS
    max_connections: ClassVar[int] = MAX_CONNECTIONS
    trusted: ClassVar[tuple[IpNetwork, ...]] = ()
    _last_refusal_log: ClassVar[float] = float("-inf")
    # Open connections per client address (not trusted ones), kept as they open and close:
    # counting through every connection on each new one slowed a flood's accepts down.
    _per_address: ClassVar[dict[str, int]] = {}

    _head_timer: asyncio.TimerHandle | None = None
    _counted: str | None = None

    def connection_made(self, transport: asyncio.Transport) -> None:  # type: ignore[override]
        super().connection_made(transport)  # adds this connection to self.connections
        why = self._refusal()
        if why is not None:
            self._log_refusal(why)
            transport.abort()
            return
        self._arm()

    def _refusal(self) -> str | None:
        if len(self.connections) > self.max_connections:
            open_now = len(self.connections) - 1
            return f"{open_now} connections are open (at most {self.max_connections})"
        address = self._address(self)
        if address is None or self._is_trusted(address):
            return None
        open_now = self._per_address.get(address, 0)
        if open_now >= self.max_per_address:
            return (
                f"{open_now} connections from {address} are open "
                f"(at most {self.max_per_address} per address)"
            )
        self._per_address[address] = open_now + 1
        self._counted = address
        return None

    def _uncount(self) -> None:
        address, self._counted = self._counted, None
        if address is None:
            return
        left = self._per_address.get(address, 1) - 1
        if left > 0:
            self._per_address[address] = left
        else:
            self._per_address.pop(address, None)

    @staticmethod
    def _address(protocol: object) -> str | None:
        client = getattr(protocol, "client", None)
        return address_key(str(client[0])) if client else None

    def _is_trusted(self, address: str) -> bool:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False
        return any(ip in network for network in self.trusted)

    @classmethod
    def _log_refusal(cls, why: str) -> None:
        now = time.monotonic()
        if now - cls._last_refusal_log < REFUSAL_LOG_INTERVAL_SECONDS:
            return
        # Set on GuardedH11Protocol itself: one warning a minute for every configured class.
        GuardedH11Protocol._last_refusal_log = now
        logger.warning("Refused new connections: %s.", why)

    # --- The request head must arrive in time ------------------------------------------------

    def _arm(self) -> None:
        self._disarm()
        self._head_timer = self.loop.call_later(self.head_timeout, self._head_timed_out)

    def _disarm(self) -> None:
        if self._head_timer is not None:
            self._head_timer.cancel()
            self._head_timer = None

    def _serving(self) -> bool:
        return self.cycle is not None and not self.cycle.response_complete

    def _head_timed_out(self) -> None:
        self._head_timer = None
        if not self._serving():  # waiting for (the rest of) a request head
            self.transport.close()

    def handle_events(self) -> None:
        super().handle_events()
        if self._serving():  # a request head has arrived
            self._disarm()

    def on_response_complete(self) -> None:
        super().on_response_complete()
        if not self.transport.is_closing() and not self._serving():
            self._arm()  # the next request's head must arrive in time too

    def connection_lost(self, exc: Exception | None) -> None:
        self._disarm()
        self._uncount()
        super().connection_lost(exc)


def protocol_class(trusted_proxies: str, max_connections: int) -> type[GuardedH11Protocol]:
    """The protocol for ``uvicorn.run(http=...)``, configured for this start."""

    class NetScopeH11Protocol(GuardedH11Protocol):
        pass

    NetScopeH11Protocol.trusted = trusted_networks(trusted_proxies)
    NetScopeH11Protocol.max_connections = max_connections
    NetScopeH11Protocol._per_address = {}
    return NetScopeH11Protocol
