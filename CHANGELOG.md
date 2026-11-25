# Changelog

Every NetScope release, newest first. A new release adds its section at the top; older
sections are never rewritten.

## 0.1.0 (2026-11-25)

The first public release: an inventory of your home network that you run yourself, with Docker
Compose, on a computer at home. You enter everything by hand; NetScope never scans or
discovers your network.

**What's in it**

- **Devices:** name, IP address, hostname, MAC address with its vendor (from an offline IEEE
  list), category, role, location, description and services (port, TCP/UDP, name, note).
  Search across every field, a category filter, sorting, and a warning when two devices share
  an IP or MAC address.
- **Categories:** 12 defaults; add, rename, recolor and delete them, each with an icon.
- **Map:** devices as boxes and links by type (Ethernet, Wi-Fi, VPN, other). Drag boxes on a
  grid and the layout is saved; click a box for its details. Works on a phone.
- **Status checks:** ping, TCP port or HTTP(S) request per device, every 30 seconds by
  default. A device is down after 2 failed checks in a row, with the reason ("Connection
  refused on port 22"). Every result is kept for 7 days (not shown yet). The interval,
  timeout, failures and history are set in Settings.
- **Dashboard:** how many checked devices are up and down, what is down now, devices by
  category, the latest edits, totals, a quick search, and a warning when the checks have
  stopped.
- **Account:** one admin, first-run setup with a one-time token from the log, password
  change, "log out other sessions", and `netscope reset-password` on the command line.
- **Backups:** JSON export and import (replace all, or merge by device name). The whole file
  is checked first, with a preview of what changes; the database is copied before every
  import.
- **Docker:** one hardened container (unprivileged, no capabilities, read-only filesystem)
  with the database on a named volume, a healthcheck, and ping without extra rights. There is
  a guide for HTTPS with Tailscale Serve.
- **Security:** argon2id password hashes, server-side sessions (30 days without use, 90 days
  at most), limited login attempts, cross-site request protection, a Content-Security-Policy,
  protection against DNS rebinding, and limits on idle and open connections (one address on the
  LAN cannot keep NetScope busy). The version is shown only after logging in.

**Not yet (planned for later):** DNS checks, SNMP, latency charts, notifications, live updates
over WebSockets, automatic map layout, several IP addresses per device.

**Known limits**

- The container has no IPv6 address: check devices by their IPv4 address.

**Docs:** [`docs/deployment.md`](docs/deployment.md) (installing it at home),
[`docs/user-guide.md`](docs/user-guide.md) (using it), [`SECURITY.md`](SECURITY.md)
(the security model and how to report a problem).
