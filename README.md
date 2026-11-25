# NetScope

**Your home network, mapped.**

NetScope is a small self-hosted web app for your home network: an inventory of every device,
a map you draw yourself, live up/down signs, and a dashboard. You run it on a computer at home
and open it in your browser.

You enter everything by hand: NetScope never scans or discovers your network. Its status
checks contact only the devices you entered and turned a check on for.

> **Version 0.1.0** (2026-11-25), the first public release. What changed:
> [`CHANGELOG.md`](CHANGELOG.md). License: [MIT](LICENSE).

## What it does

- **Devices** with their IP address, hostname, MAC address and its vendor (from an offline IEEE
  list), category, role, location, description and services (port, TCP/UDP, name, note).
  Search across every field, filter by category, sort; a warning when two devices share an IP
  or MAC address.
- **Categories** with colors and icons (12 defaults: Router, Switch, Server, NAS, ...).
- **A map:** devices as boxes, links by type (Ethernet, Wi-Fi, VPN, other). Drag the boxes; the
  layout is saved. Works on a phone.
- **Status checks:** ping, a TCP port or an HTTP(S) request per device, every 30 seconds by
  default. A device turns red after 2 failed checks in a row, with the reason ("Connection
  refused on port 22"); every result is kept for 7 days.
- **A dashboard:** what is up and down, what is down now, devices by category, the latest edits,
  totals and a quick search.
- **One admin account** with password change and "log out other sessions".
- **Backups:** a JSON export and import (replace all, or merge by device name), checked
  completely before anything is written, and a copy of the database before every import.
- **Docker Compose:** one hardened container, the database on a Docker volume.

It is not a monitoring suite (no alerts, no SNMP, no charts yet) and not meant to be reachable
from the internet.

## Install (Docker)

You need a Linux computer at home that is on when you want checks to run (a home server, a
NAS, a laptop, or a Raspberry Pi with a 64-bit OS), on x86-64 or 64-bit ARM (only x86-64 has
been tested so far), with Git, Docker Engine and the Docker Compose and Buildx plugins. [`docs/deployment.md`](docs/deployment.md) shows every step, including how to prepare
the computer.

```bash
git clone https://github.com/123timsolotech/Netscope-open-source.git ~/netscope
```

```bash
cd ~/netscope
```

```bash
docker compose up -d
```

The first start builds the image (a few minutes; later starts take seconds). Then get the one-time setup token from the
log (the last one, if there are several):

```bash
docker compose logs netscope | grep -a -A2 "setup token:" | tail -1
```

Open `http://<that computer's IP address>:8000`, paste the token, and choose a username and a
password (at least 20 characters). That's it.

To try it with a made-up home network first (15 devices with services and links; their checks
are off, because the made-up addresses might be real devices of yours):

```bash
docker compose exec netscope netscope seed --demo
```

To start over with an empty NetScope afterwards (this deletes everything, the admin account
included; you set it up again with a new token):

```bash
docker compose down -v
```

```bash
docker compose up -d
```

## Using it

[`docs/user-guide.md`](docs/user-guide.md) covers everything you do day to day: adding devices,
which check suits which device, the map, the dashboard, backups and restores, and what to do
when something is wrong. [`docs/deployment.md`](docs/deployment.md) covers running it: updates,
backups of the database, HTTPS with Tailscale Serve, security notes and troubleshooting.

**Update** to a new version (the database is migrated at startup, with a backup first):

```bash
git pull
```

```bash
docker compose up -d
```

## Settings

Settings you change in the app (check interval, timeout, history, categories) live in its
database. Startup settings go into a file `.env` next to `docker-compose.yml`; start from
[`.env.example`](.env.example). Every line is optional:

| Setting | Meaning |
| --- | --- |
| `NETSCOPE_PUBLISH` | Where the port is published: `8000` (the LAN, the default) or `127.0.0.1:8000` (this computer only, for Tailscale Serve) |
| `NETSCOPE_ALLOWED_HOSTS` | Extra host names NetScope answers to, such as `nas.fritz.box` (IP addresses, single-word names, `.local`, `.home.arpa`, `.internal` and `.ts.net` names always work) |
| `NETSCOPE_TRUSTED_PROXIES` | The reverse proxy whose `X-Forwarded-*` headers count (behind Tailscale Serve: `172.30.240.1`) |
| `NETSCOPE_LOG_LEVEL` | `DEBUG`, `INFO` (default), `WARNING` or `ERROR` |
| `NETSCOPE_ADMIN_USERNAME`, `NETSCOPE_ADMIN_PASSWORD` | Create the admin at the first start instead of using the setup token (remove the password afterwards) |
| `NETSCOPE_SETUP_TOKEN` | Your own setup token instead of a random one (at least 20 characters) |

After changing `.env`, run `docker compose up -d` again.

## Status checks

Each device can have one check: **ping**, a **TCP port** (up when a connection opens) or an
**HTTP(S)** request (up for 200-399, or 401/403 when a login is required). The check goes to
the device's IP address, or its hostname if it has none. NetScope checks every 30 seconds by
default, at most 50 at once; a device turns red after 2 failed checks in a row. Which check
suits which device: [`docs/user-guide.md`](docs/user-guide.md), section 8.

**Ping without root rights.** NetScope pings unprivileged. In Docker that works without any
setting (if not: [`docs/deployment.md`](docs/deployment.md), section 3). Without Docker, on
Linux, the `net.ipv4.ping_group_range` setting must include NetScope's group; Ubuntu 20.04 and
later allow every group by default. Check it:

```bash
sysctl net.ipv4.ping_group_range
```

If it does not show `0 2147483647`, allow it, and put the same setting in a file in
`/etc/sysctl.d/` to keep it after a reboot:

```bash
sudo sysctl -w net.ipv4.ping_group_range="0 2147483647"
```

Otherwise ping checks fail with "Ping is not permitted for NetScope on this computer"; TCP and
HTTP checks are not affected. On Windows, ping works without admin rights.

## Security

NetScope is made for one admin on a home network. Do not forward its port on your router; for
access from away, use a VPN such as Tailscale. [`SECURITY.md`](SECURITY.md) describes what it
protects against, what it does not, and how to report a security problem privately.

## Run it without Docker

For development, or on a computer without Docker. You need Python 3.13 with
[uv](https://docs.astral.sh/uv/) and Node.js 24 with npm. Build the web interface once:

```bash
cd frontend
npm ci
npm run build
cd ..
```

Then start NetScope like in production (one process, the web interface on
http://127.0.0.1:8000). The database is created at `backend/data/netscope.db`, and the setup
token is printed in this terminal. Settings go into `backend/.env` (start from
[`backend/.env.example`](backend/.env.example)); to open it from other devices, set
`NETSCOPE_HOST=0.0.0.0`.

```bash
cd backend
uv sync
uv run python -m app
```

`python -m app` always runs exactly one worker (the status monitor runs inside it) and limits
connections (10 s for a request to arrive, at most 64 from one address). While
developing, `uv run uvicorn app.main:app --reload --port 8000` in `backend/` and `npm run dev`
in `frontend/` (http://localhost:5173) reload on every change. Useful commands, from `backend/`:

```bash
uv run netscope reset-password
```

```bash
uv run netscope seed --demo
```

```bash
uv run python ../scripts/update_oui.py
```

The last one refreshes the offline MAC vendor list (`backend/app/data/oui.csv`) from the IEEE;
it is the only command that contacts the internet. The API is described by
[`frontend/src/api/generated/openapi.json`](frontend/src/api/generated/openapi.json) (after an
API change: `uv run python ../scripts/export_openapi.py`, then `npm run gen:api` in
`frontend/`).

## Project layout

```text
backend/            FastAPI app (api, services, models, schemas, monitor, core), migrations
frontend/           React + TypeScript + Vite + Tailwind CSS + React Flow
docs/               user-guide.md (using it), deployment.md (running it with Docker)
scripts/            update_oui.py (the MAC vendor list), export_openapi.py (the API schema)
Dockerfile          the image: builds the web interface, then a Python-only runtime
docker-compose.yml  one container, the database on a volume (settings: .env.example)
```

## About this repository

This is the public copy of NetScope: each release is published here as it is. The code is
developed in a separate repository together with its tests; comments in the code that mention
design notes ("decision M6.6", "brief section 7") refer to that project's notes, which are not
part of this copy.

## License

[MIT](LICENSE).

Third-party parts: the components in `frontend/src/components/ui` come from
[shadcn/ui](https://ui.shadcn.com) (MIT, copyright 2023 shadcn). The MAC vendor list
(`backend/app/data/oui.csv`) is built from the IEEE Registration Authority's public listings and
is not covered by this project's license. NetScope is built with FastAPI, SQLAlchemy, React,
React Flow, Tailwind CSS, Lucide icons and the Inter font, each under its own license
(installed when you build it).
