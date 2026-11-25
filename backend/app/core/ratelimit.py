"""In-memory limit on failed attempts (brief section 7: 5 failed logins per minute per IP).

Kept in memory, which is enough because NetScope runs exactly one process. The counts reset
when the app restarts.
"""

import ipaddress
import math
import threading
import time
from collections import deque
from collections.abc import Callable

MAX_FAILURES = 5
WINDOW_SECONDS = 60.0


def address_key(client_ip: str) -> str:
    """The rate-limit key for a client address: the address in canonical form.

    IPv4-mapped IPv6 (``::ffff:192.0.2.1``) counts as the IPv4 address, and IPv6 spellings
    of one address share a key. Not per /64 network: every device on a home LAN shares one
    /64, so one bad device would lock everyone out (decided in the M2 security audit).
    Anything that is not an IP address (the test client) is used as it is.
    """
    try:
        address = ipaddress.ip_address(client_ip.strip("[]"))
    except ValueError:
        return client_ip
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return str(address.ipv4_mapped)
    return str(address)


class FailureRateLimiter:
    """Limits attempts per key (for example ``("login", ip)``) in a sliding time window.

    Attempts are counted when they start and cleared on success, so the limit applies to
    failed attempts (brief section 7).
    """

    def __init__(
        self,
        max_failures: int = MAX_FAILURES,
        window_seconds: float = WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._clock = clock
        self._failures: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()
        self._last_sweep = clock()

    def _expire(self, key: tuple[str, str], now: float) -> deque[float] | None:
        """Drop ``key``'s attempts older than the window; None if none are left."""
        times = self._failures.get(key)
        if times is None:
            return None
        cutoff = now - self.window_seconds
        while times and times[0] <= cutoff:
            times.popleft()
        if not times:
            del self._failures[key]
            return None
        return times

    def _sweep(self, now: float) -> None:
        """Forget idle keys, at most once per window. Checking every key on every attempt
        made each attempt slower as keys piled up (security audit, M2)."""
        if now - self._last_sweep < self.window_seconds:
            return
        self._last_sweep = now
        for key in list(self._failures):
            self._expire(key, now)

    def attempt(self, key: tuple[str, str]) -> int | None:
        """Count an attempt for ``key``, atomically.

        Returns None if the attempt may go ahead (it is counted now, before the slow
        password check, so parallel requests cannot all slip through), or the number of
        seconds to wait. A success should call ``reset``, so in effect only failures count.
        """
        with self._lock:
            now = self._clock()
            self._sweep(now)
            times = self._expire(key, now)
            if times is not None and len(times) >= self.max_failures:
                # Allowed again once enough of the oldest attempts leave the window.
                wait = times[-self.max_failures] + self.window_seconds - now
                return max(1, math.ceil(wait))
            self._failures.setdefault(key, deque()).append(now)
            return None

    def reset(self, key: tuple[str, str]) -> None:
        """Forget attempts for ``key`` (after a successful login or setup)."""
        with self._lock:
            self._failures.pop(key, None)
