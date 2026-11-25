"""IP address, MAC address and hostname checks (brief section 6). Pure functions, no I/O."""

import ipaddress
import re

# Explicit ASCII classes: \d and \w would also match non-ASCII digits and letters.
_HEX = "[0-9A-Fa-f]"
MAC_PATTERNS = (
    re.compile(rf"{_HEX}{{2}}([:-]){_HEX}{{2}}(?:\1{_HEX}{{2}}){{4}}"),  # aa:bb:.. / aa-bb-..
    re.compile(rf"{_HEX}{{4}}\.{_HEX}{{4}}\.{_HEX}{{4}}"),  # aabb.ccdd.eeff (Cisco style)
    re.compile(rf"{_HEX}{{12}}"),  # aabbccddeeff
)
LOCALLY_ADMINISTERED_BIT = 0x02  # second-lowest bit of the first octet
GROUP_BIT = 0x01  # lowest bit of the first octet: multicast / broadcast, never a device's own
ZERO_MAC = "00:00:00:00:00:00"

HOSTNAME_MAX_LENGTH = 253
# A label: letters, digits, "_" and "-", 1-63 characters, no "-" at either end.
# Underscores are not valid in DNS hostnames, but many home devices use them.
_HOSTNAME_LABEL = re.compile(r"[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?")


def normalize_ip(value: str) -> str:
    """Valid IPv4 or IPv6 address in its canonical form (IPv6 compressed, lower case).

    Raises ValueError with a message for the user.
    """
    text = value.strip()
    if "%" in text:
        raise ValueError("IPv6 zone ids such as %eth0 are not supported.")
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        raise ValueError("Enter a valid IPv4 or IPv6 address.") from None
    return str(address)


def normalize_mac(value: str) -> str:
    """MAC address as ``AA:BB:CC:DD:EE:FF``.

    Accepts ``aa:bb:cc:dd:ee:ff``, ``aa-bb-cc-dd-ee-ff``, ``aabb.ccdd.eeff`` and
    ``aabbccddeeff``, in any letter case. A device's own address is never a multicast or
    broadcast address (IEEE 802) and never all zeros (a placeholder), so those are rejected:
    they are usually copied by mistake from a router's table. Raises ValueError with a
    message for the user.
    """
    text = value.strip()
    if not any(pattern.fullmatch(text) for pattern in MAC_PATTERNS):
        raise ValueError("Enter a MAC address like AA:BB:CC:DD:EE:FF.")
    digits = re.sub(r"[^0-9A-Fa-f]", "", text).upper()
    mac = ":".join(digits[i : i + 2] for i in range(0, 12, 2))
    if int(digits[:2], 16) & GROUP_BIT:
        raise ValueError("This is a multicast or broadcast address, not a device's own MAC.")
    if mac == ZERO_MAC:
        raise ValueError(f"{ZERO_MAC} is a placeholder, not a real MAC address.")
    return mac


def is_locally_administered(mac: str) -> bool:
    """True if the locally-administered bit is set (randomized / private MACs).

    ``mac`` must already be normalized.
    """
    return bool(int(mac[:2], 16) & LOCALLY_ADMINISTERED_BIT)


def hostname_problem(value: str) -> str | None:
    """Why ``value`` is not a usable hostname, or None if it is."""
    name = value.removesuffix(".")
    if not name:
        return "Enter a hostname."
    if len(name) > HOSTNAME_MAX_LENGTH:
        return f"A hostname has at most {HOSTNAME_MAX_LENGTH} characters."
    labels = name.split(".")
    if not all(_HOSTNAME_LABEL.fullmatch(label) for label in labels):
        return (
            "Use letters, digits, hyphens and underscores, separated by dots "
            "(for example nas.local)."
        )
    if labels[-1].isdigit():
        return "This looks like an IP address. Put it in the IP address field."
    return None
