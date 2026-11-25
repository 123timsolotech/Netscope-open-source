"""Default categories and demo data (brief sections 2 and 9, M3). Plain data, no imports.

The default categories are created once on a new database (migration 0002) and can be
re-added with ``netscope seed``. The demo data is only added by ``netscope seed --demo``.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DefaultCategory:
    name: str
    icon: str  # Lucide icon name
    color: str  # distinct, readable on the navy background; changeable in the UI


DEFAULT_CATEGORIES: tuple[DefaultCategory, ...] = (
    DefaultCategory("Router", "router", "#60a5fa"),
    DefaultCategory("Switch", "network", "#818cf8"),
    DefaultCategory("Server", "server", "#a78bfa"),
    DefaultCategory("NAS", "hard-drive", "#c084fc"),
    DefaultCategory("Access point", "wifi", "#5eead4"),
    DefaultCategory("PC", "monitor", "#7dd3fc"),
    DefaultCategory("Phone", "smartphone", "#f472b6"),
    DefaultCategory("IoT", "cpu", "#bef264"),
    DefaultCategory("Printer", "printer", "#e879f9"),
    DefaultCategory("Camera", "cctv", "#fdba74"),
    DefaultCategory("TV / Media", "tv", "#f0abfc"),
    DefaultCategory("Other", "shapes", "#94a3b8"),
)

# Demo home network. Every check is configured but turned OFF: these addresses are made up
# and may belong to real devices on the user's network, which NetScope must not contact
# unless the user turns a check on (brief section 1). "category" is a default category name.
DEMO_DEVICES: tuple[dict[str, Any], ...] = (
    {
        "name": "router",
        "category": "Router",
        "ip_address": "192.168.1.1",
        "role": "Internet gateway, DHCP",
        "location": "Hallway cabinet",
        "check_type": "icmp",
        "services": [
            {"port": 53, "protocol": "udp", "name": "DNS"},
            {"port": 80, "name": "Web interface"},
        ],
    },
    {
        "name": "switch-office",
        "category": "Switch",
        "ip_address": "192.168.1.2",
        "role": "8-port managed switch",
        "location": "Office desk",
        "check_type": "icmp",
        "services": [{"port": 80, "name": "Web interface"}],
    },
    {
        "name": "switch-living-room",
        "category": "Switch",
        "role": "5-port unmanaged switch",
        "location": "Living room, behind the TV",
        "description": "Unmanaged, so it has no IP address and cannot be checked.",
    },
    {
        "name": "ap-hallway",
        "category": "Access point",
        "ip_address": "192.168.1.4",
        "role": "Wi-Fi access point",
        "location": "Hallway ceiling",
        "check_type": "icmp",
    },
    {
        "name": "pihole",
        "category": "Server",
        "hostname": "pihole.lan",
        "ip_address": "192.168.1.5",
        "mac_address": "DC:A6:32:12:34:56",
        "role": "DNS ad blocker",
        "location": "Office shelf",
        "check_type": "http",
        "check_path": "/admin/",
        "services": [
            {"port": 53, "protocol": "udp", "name": "DNS"},
            {"port": 53, "protocol": "tcp", "name": "DNS"},
            {"port": 80, "name": "Admin interface"},
        ],
    },
    {
        "name": "nas",
        "category": "NAS",
        "hostname": "nas.lan",
        "ip_address": "192.168.1.10",
        "mac_address": "00:11:32:AB:CD:EF",
        "role": "File storage and backups",
        "location": "Office shelf",
        "check_type": "tcp",
        "check_port": 445,
        "services": [
            {"port": 445, "name": "SMB file shares"},
            {"port": 2049, "name": "NFS"},
            {"port": 5000, "name": "Web interface"},
        ],
    },
    {
        "name": "media-server",
        "category": "Server",
        "ip_address": "192.168.1.20",
        "role": "Plex media server",
        "location": "Office shelf",
        "check_type": "http",
        "check_port": 32400,
        "check_path": "/identity",
        "services": [{"port": 32400, "name": "Plex", "note": "Remote access is off."}],
    },
    {
        "name": "homeassistant",
        "category": "Server",
        "ip_address": "192.168.1.30",
        "role": "Home automation",
        "location": "Office shelf",
        "check_type": "http",
        "check_port": 8123,
        "services": [{"port": 8123, "name": "Home Assistant"}],
    },
    {
        "name": "thinkpad",
        "category": "Server",
        "hostname": "thinkpad.lan",
        "ip_address": "192.168.1.40",
        "role": "Runs NetScope (lid closed, always on)",
        "location": "Office shelf",
        "check_type": "icmp",
        "services": [
            {"port": 22, "name": "SSH"},
            {"port": 8000, "name": "NetScope"},
        ],
    },
    {
        "name": "desktop-pc",
        "category": "PC",
        "ip_address": "192.168.1.50",
        "role": "Workstation",
        "location": "Office desk",
        "check_type": "icmp",
    },
    {
        "name": "printer",
        "category": "Printer",
        "ip_address": "192.168.1.60",
        "role": "Laser printer",
        "location": "Office",
        "check_type": "tcp",
        "check_port": 631,
        "services": [
            {"port": 631, "name": "IPP printing"},
            {"port": 9100, "name": "Raw printing"},
        ],
    },
    {
        "name": "living-room-tv",
        "category": "TV / Media",
        "ip_address": "192.168.1.70",
        "role": "Smart TV",
        "location": "Living room",
        "check_type": "icmp",
    },
    {
        "name": "camera-front-door",
        "category": "Camera",
        "ip_address": "192.168.1.80",
        "role": "Door camera",
        "location": "Front door",
        "check_type": "tcp",
        "check_port": 554,
        "services": [{"port": 554, "name": "RTSP stream"}],
    },
    {
        "name": "phone",
        "category": "Phone",
        "mac_address": "DA:A1:19:5C:3E:07",
        "role": "Personal phone",
        "description": "Uses a private (randomized) Wi-Fi address and gets its IP from DHCP.",
    },
    {
        "name": "smart-plug-desk",
        "category": "IoT",
        "ip_address": "192.168.1.90",
        "role": "Smart plug for the desk lamp",
        "location": "Office desk",
    },
)

# (device, device, link type, label)
DEMO_LINKS: tuple[tuple[str, str, str, str | None], ...] = (
    ("router", "switch-office", "ethernet", "LAN 1"),
    ("router", "switch-living-room", "ethernet", "LAN 2"),
    ("router", "ap-hallway", "ethernet", "LAN 3"),
    ("switch-office", "pihole", "ethernet", None),
    ("switch-office", "nas", "ethernet", None),
    ("switch-office", "media-server", "ethernet", None),
    ("switch-office", "homeassistant", "ethernet", None),
    ("switch-office", "thinkpad", "ethernet", None),
    ("switch-office", "desktop-pc", "ethernet", None),
    ("switch-living-room", "living-room-tv", "ethernet", None),
    ("ap-hallway", "printer", "wifi", None),
    ("ap-hallway", "camera-front-door", "wifi", None),
    ("ap-hallway", "phone", "wifi", None),
    ("ap-hallway", "smart-plug-desk", "wifi", None),
    ("phone", "thinkpad", "vpn", "Tailscale"),
)

# Where the demo devices sit on the map (M5): a tree from left to right, router, then
# switches and the access point, then the devices plugged into each. Top-left corners, on the
# map's 20 px snap grid. Shifted down as a whole if the database already has devices.
DEMO_POSITIONS: dict[str, tuple[float, float]] = {
    "router": (0, 660),
    "switch-office": (340, 240),
    "ap-hallway": (340, 740),
    "switch-living-room": (340, 1000),
    "pihole": (680, 0),
    "nas": (680, 100),
    "media-server": (680, 200),
    "homeassistant": (680, 300),
    "desktop-pc": (680, 400),
    "thinkpad": (680, 500),
    "phone": (680, 600),
    "printer": (680, 700),
    "camera-front-door": (680, 800),
    "smart-plug-desk": (680, 900),
    "living-room-tv": (680, 1000),
}
