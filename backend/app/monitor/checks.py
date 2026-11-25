"""The three status checks (brief section 2): ICMP ping, TCP connect, HTTP(S) request.

A check contacts exactly one address: the device's IP, or its hostname (decision M3.10),
for a device whose check the user turned on. Nothing here follows a redirect, uses a proxy
from the environment or reads a response body.

What counts (owner decisions, M6):

- **ICMP:** up when the device answers one echo request. Latency: the round trip.
- **TCP:** up when a connection to the port opens. Latency: the time to open it (the name
  lookup of a hostname is not counted).
- **HTTP:** one ``GET``; up when the status is 200-399, or 401/403 (login required: the
  service answers). Redirects are not followed (they could lead to another host). The body is
  not read. Latency: until the response headers arrived (connect, TLS, server), including the
  name lookup of a hostname.

The overall timeout is the monitor's (``scheduler.py``); ``timeout`` is passed on so the
libraries' own timeouts agree with it. Failure reasons are fixed texts plus numbers and
operating-system messages, never text from the device's answer, because they are shown in the
UI.
"""

import asyncio
import errno
import http
import ipaddress
import logging
import socket
import ssl
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import cache

import httpx
import icmplib

from app.models import CheckScheme, CheckType
from app.services.status import CheckJob

logger = logging.getLogger("netscope.monitor")

# Without the version: devices need not know it (final security audit, M8).
USER_AGENT = "NetScope (status check)"
DEFAULT_PORTS = {CheckScheme.HTTP: 80, CheckScheme.HTTPS: 443}
# 401 and 403: the service answers, it wants a login (owner decision, M6).
LOGIN_REQUIRED = frozenset({401, 403})
INVALID_URL = "The check's address is not valid."
PING_NOT_PERMITTED = (
    "Ping is not permitted for NetScope on this computer (see the README, status checks)."
)


@dataclass(frozen=True)
class CheckOutcome:
    is_up: bool
    latency_ms: float | None = None
    error: str | None = None


# What the monitor calls: (job, timeout in seconds) -> outcome. Tests pass fakes.
Checker = Callable[[CheckJob, float], Awaitable[CheckOutcome]]


class CheckFailedError(Exception):
    """The device did not pass the check; ``message`` says why (shown to the user)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


async def run_check(job: CheckJob, timeout: float) -> CheckOutcome:
    """Run the device's check. Never raises for a failed check: the outcome says why."""
    try:
        if job.check_type == CheckType.ICMP:
            latency = await ping(job.target, timeout)
        elif job.check_type == CheckType.TCP:
            if job.port is None:  # the device rules require a port
                raise CheckFailedError("A TCP check needs a port.")
            latency = await tcp_connect(job.target, job.port)
        elif job.check_type == CheckType.HTTP:
            latency = await http_get(job, timeout)
        else:
            raise CheckFailedError("No check type.")
    except CheckFailedError as failure:
        return CheckOutcome(is_up=False, error=failure.message)
    return CheckOutcome(is_up=True, latency_ms=round(latency, 3))


# --- Name lookup ---------------------------------------------------------------------------


async def resolve(target: str) -> list[str]:
    """The target's IP addresses: itself if it is one, else every address the system's
    resolver gives for the hostname, IPv4 first (as icmplib does: a home device's IPv6 record
    is often stale, or its service listens on IPv4 only)."""
    try:
        return [str(ipaddress.ip_address(target))]
    except ValueError:
        pass
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(target, None, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise CheckFailedError(f"Hostname not found: {target}") from None
    addresses = list(dict.fromkeys(str(info[4][0]) for info in infos))
    if not addresses:
        raise CheckFailedError(f"Hostname not found: {target}")
    return sorted(addresses, key=lambda address: ":" in address)  # stable: IPv4 first


# --- ICMP ----------------------------------------------------------------------------------

_ping_warning_logged = False


async def ping(target: str, timeout: float) -> float:
    """One echo request without root rights (``privileged=False``; ignored on Windows), to
    the first address (IPv4 first)."""
    address = (await resolve(target))[0]
    try:
        host = await icmplib.async_ping(address, count=1, timeout=timeout, privileged=False)
    except icmplib.SocketPermissionError:
        _log_ping_not_permitted()
        raise CheckFailedError(PING_NOT_PERMITTED) from None
    except icmplib.ICMPLibError as error:
        raise CheckFailedError(f"Ping failed: {type(error).__name__}") from None
    except OSError as error:
        raise CheckFailedError(describe_os_error(error)) from None
    if not host.is_alive:
        raise CheckFailedError(f"No reply to ping within {timeout:g} s")
    return float(host.avg_rtt)


def _log_ping_not_permitted() -> None:
    global _ping_warning_logged
    if _ping_warning_logged:
        return
    _ping_warning_logged = True
    logger.warning(
        "ICMP checks fail: this computer does not allow ping without root rights. On Linux, "
        "allow it with: sysctl -w net.ipv4.ping_group_range='0 2147483647' (and in "
        "/etc/sysctl.d to keep it). In Docker the host's setting does not count: add the "
        "sysctls entry from docs/deployment.md (section 3). TCP and HTTP checks are not "
        "affected."
    )


# --- TCP -----------------------------------------------------------------------------------


async def tcp_connect(target: str, port: int) -> float:
    """Opens a connection to the first address that accepts one (each in turn, IPv4 first).
    The latency is that connection's. The reason of a failure is the first address's: a later
    one (IPv6 on a host without it) would hide "Connection refused" behind "Address family
    not supported" (found in the M6 review)."""
    failure: OSError | None = None
    for address in await resolve(target):
        started = time.perf_counter()
        try:
            _reader, writer = await asyncio.open_connection(address, port)
        except OSError as error:
            failure = failure or error
            continue
        latency = (time.perf_counter() - started) * 1000
        writer.close()  # closes in the background; the check is done
        return latency
    if failure is None:  # resolve() returns at least one address
        raise CheckFailedError(f"Hostname not found: {target}")
    raise CheckFailedError(describe_os_error(failure, port))


# --- HTTP ----------------------------------------------------------------------------------


def build_url(job: CheckJob) -> httpx.URL:
    """``scheme://target[:port]/path`` from the parts, never with urljoin (decision M3.10).

    The path always starts with a single ``/`` and has no spaces or backslashes (checked when
    saved), so the address part ends where it is put. As a second line of defense, the URL is
    parsed back and must point at the device's address and port.
    """
    scheme = CheckScheme(job.scheme)
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None
    try:
        ip = ipaddress.ip_address(job.target)
    except ValueError:
        ip, host = None, job.target
    else:
        host = f"[{ip.compressed}]" if ip.version == 6 else ip.compressed
    port = "" if job.port is None else f":{job.port}"
    try:
        url = httpx.URL(f"{scheme.value}://{host}{port}{job.path}")
    except httpx.InvalidURL:
        raise CheckFailedError(INVALID_URL) from None
    if (
        url.scheme != scheme.value
        or not _same_host(url.raw_host.decode("ascii", errors="replace"), job.target, ip)
        or (url.port or DEFAULT_PORTS[scheme]) != (job.port or DEFAULT_PORTS[scheme])
        or not url.raw_path.startswith(b"/")
    ):
        raise CheckFailedError(INVALID_URL)
    return url


def _same_host(
    host: str, target: str, ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None
) -> bool:
    """``host`` is the URL's host as sent (ASCII: an IDN stays in its xn-- form)."""
    if ip is None:
        return host == target.lower()
    try:
        return ipaddress.ip_address(host) == ip
    except ValueError:
        return False


def is_up_status(status_code: int) -> bool:
    return 200 <= status_code <= 399 or status_code in LOGIN_REQUIRED


async def http_get(job: CheckJob, timeout: float) -> float:
    url = build_url(job)
    started = time.perf_counter()
    try:
        async with (
            httpx.AsyncClient(
                verify=tls_context(job.verify_tls),
                timeout=timeout,
                follow_redirects=False,
                # Without this, httpx would use HTTP(S)_PROXY from the environment and send
                # checks of LAN devices to a proxy.
                trust_env=False,
                # A new connection for every check: a kept-alive one would not test connecting.
                limits=httpx.Limits(max_keepalive_connections=0),
                headers={"User-Agent": USER_AGENT},
            ) as client,
            client.stream("GET", url) as response,
        ):
            latency = (time.perf_counter() - started) * 1000
            status_code = response.status_code
    except httpx.TimeoutException:
        raise CheckFailedError(f"Timed out after {timeout:g} s") from None
    except httpx.HTTPError as error:
        raise CheckFailedError(describe_http_error(error, job)) from None
    if not is_up_status(status_code):
        raise CheckFailedError(describe_status(status_code))
    return latency


def describe_status(status_code: int) -> str:
    try:
        phrase = http.HTTPStatus(status_code).phrase
    except ValueError:
        return f"HTTP {status_code}"
    return f"HTTP {status_code} ({phrase})"


def prepare() -> None:
    """Make the TLS settings once, ahead of the first round: loading the trusted certificates
    takes tens of milliseconds and, done during a round, would block the event loop and add
    to every latency measured meanwhile. Blocking: run it in a thread."""
    tls_context(True)
    tls_context(False)


@cache
def tls_context(verify: bool) -> ssl.SSLContext:
    """Verifying: the system's trusted certificates (where a home CA would be added).

    Not verifying (the default, decision M3.10): any certificate, and old TLS versions and
    ciphers too, because the check only asks whether the device answers and sends nothing
    secret. Old printers and routers often offer nothing else.
    """
    context = ssl.create_default_context()
    if verify:
        return context
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        context.minimum_version = ssl.TLSVersion.MINIMUM_SUPPORTED
        context.set_ciphers("ALL:@SECLEVEL=0")
    except (ssl.SSLError, ValueError):  # an OpenSSL build without them: keep its defaults
        logger.debug("Old TLS versions are not available for HTTPS checks.")
    return context


def describe_http_error(error: httpx.HTTPError, job: CheckJob) -> str:
    scheme = CheckScheme(job.scheme)
    port = job.port or DEFAULT_PORTS[scheme]
    for cause in _causes(error):
        if isinstance(cause, ssl.SSLCertVerificationError):
            reason = cause.verify_message or "not trusted"
            return f"Certificate not accepted: {reason}"
        if isinstance(cause, ssl.SSLError):
            return "TLS handshake failed (is this port HTTPS?)"
        if isinstance(cause, socket.gaierror):
            return f"Hostname not found: {job.target}"
        if isinstance(cause, OSError) and cause.errno is not None:
            return describe_os_error(cause, port)
    if isinstance(error, httpx.RemoteProtocolError):
        # Also a server that accepts and closes the connection: no guess about the cause.
        return "No valid HTTP answer"
    if isinstance(error, httpx.ConnectError):
        return "Connection failed"
    return "Request failed"


def _causes(error: BaseException) -> list[BaseException]:
    seen: list[BaseException] = []
    current: BaseException | None = error
    while current is not None and current not in seen and len(seen) < 10:
        seen.append(current)
        current = current.__cause__ or current.__context__
    return seen


# --- Errors --------------------------------------------------------------------------------

# By name: not every platform has every code (Windows maps them to its own numbers).
_OS_ERRORS = {
    code: text
    for name, text in (
        ("ECONNREFUSED", "Connection refused"),
        ("ECONNRESET", "Connection reset"),
        ("EHOSTUNREACH", "Host unreachable"),
        ("ENETUNREACH", "Network unreachable"),
        ("ETIMEDOUT", "Timed out"),
        ("EHOSTDOWN", "Host is down"),
        ("EADDRNOTAVAIL", "Address not available"),
    )
    if (code := getattr(errno, name, None)) is not None
}


def describe_os_error(error: OSError, port: int | None = None) -> str:
    text = _OS_ERRORS.get(error.errno or 0)
    if text is None:
        detail = error.strerror or type(error).__name__
        text = f"Connection failed: {detail}"
    if port is not None and error.errno == errno.ECONNREFUSED:
        return f"{text} on port {port}"
    return text
