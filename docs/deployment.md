# Running NetScope at home (Docker Compose)

NetScope runs as **one container** on a computer at home (called the server below: a home
server, a NAS, a laptop, or a Raspberry Pi with a 64-bit OS; x86-64 or 64-bit ARM, only x86-64
tested so far). The status checks run from there, so they run while that computer is on, and
NetScope continues by itself after a boot. Any Linux computer with Docker works; the commands
below use Arch Linux as the example.

- The web interface and the API on port **8000**.
- The SQLite database on a Docker volume (`netscope_netscope-data`, mounted at `/data`).
- Exactly one worker inside (the status monitor lives in the app process).
- Restarts on its own after a crash, a reboot or a Docker update (`restart: unless-stopped`).

Commands below run from the folder you cloned NetScope into (`~/netscope`). If your user is not
in the `docker` group, put `sudo` in front of every `docker` command.

## 1. Prepare the computer

Install Docker Engine, the Compose and Buildx plugins, and git. On Arch Linux:

```bash
sudo pacman -Syu docker docker-compose docker-buildx git
```

On other distributions, follow Docker's guide for yours (https://docs.docker.com/engine/install/)
and install git with its package manager. The rest of this section is for Arch; on other
systems the same steps have their own commands.

If that updated the kernel (the `linux` package), reboot now: until then Docker may fail to
start, because the running kernel's modules are gone. Then start Docker, now and at every boot:

```bash
sudo systemctl enable --now docker.service
```

Optional: use `docker` without `sudo` (log out and in afterwards). Members of the `docker` group
can do anything as root on this computer, so only add your own account:

```bash
sudo usermod -aG docker "$USER"
```

### A laptop as a server

These are the usual Arch steps (see the Arch Wiki pages "Power management" and "TLP"); NetScope
itself does not need them, but the checks stop when the laptop sleeps.

- **Keep running with the lid closed.** Create `/etc/systemd/logind.conf.d/lid.conf`:

  ```bash
  sudo mkdir -p /etc/systemd/logind.conf.d
  ```

  ```bash
  printf '[Login]\nHandleLidSwitch=ignore\nHandleLidSwitchExternalPower=ignore\nHandleLidSwitchDocked=ignore\n' | sudo tee /etc/systemd/logind.conf.d/lid.conf
  ```

  Reboot to apply it.
- **No suspend or hibernation.** With a desktop environment, set "never suspend" in its power
  settings. Without one (or to be sure), turn sleep off completely:

  ```bash
  sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
  ```

- **Keep it plugged in, with a charge limit** to protect the battery, if the laptop supports
  one (ThinkPads do). With TLP (`sudo pacman -S tlp`, then
  `sudo systemctl enable --now tlp.service`), set in `/etc/tlp.conf`:

  ```ini
  START_CHARGE_THRESH_BAT0=75
  STOP_CHARGE_THRESH_BAT0=80
  ```

  Check it with `cat /sys/class/power_supply/BAT0/charge_control_end_threshold` (shows `80`).

## 2. Install and start NetScope

Get NetScope (no GitHub account needed):

```bash
git clone https://github.com/123timsolotech/Netscope-open-source.git ~/netscope
```

```bash
cd ~/netscope
```

Optional settings go into a file `.env` next to `docker-compose.yml` (start from
[`.env.example`](../.env.example)). The most common one: the host name you type in the browser,
if it has dots and is not a `.local` / `.home.arpa` / `.internal` / `.ts.net` name (see
"Host names" below):

```bash
cp .env.example .env
```

Build and start (the first build takes a few minutes; later starts take seconds):

```bash
docker compose up -d
```

Read the one-time setup token from the log (if NetScope restarted before you finished setup,
the log shows several: this prints the last one; copy and paste it, it is case-sensitive):

```bash
docker compose logs netscope | grep -a -A2 "setup token:" | tail -1
```

Open `http://<this computer's IP address>:8000` from any device on your network
(`ip -4 -br addr` shows the address, on the `wl…` or `en…` line; `http://homeserver:8000` works
only if your router knows that name), enter the token, choose a username and a password of at least 20 characters. The
token changes on every restart until setup is done.

Instead of the token you can create the admin on the first start: put
`NETSCOPE_ADMIN_PASSWORD='...'` (in single quotes, so characters such as `$` and `#` arrive
unchanged; optionally also `NETSCOPE_ADMIN_USERNAME`) into `.env` and start. Then **delete the
password line again and run `docker compose up -d`**: the container keeps the value it was
started with until it is recreated. It is ignored once the admin exists, but it should not stay
on disk.

Values in `.env` with `$`, `#` or spaces in them belong in single quotes, the same way.

### Host names

NetScope answers only to names it can really be reached under (protection against DNS
rebinding). These always work: IP addresses, `localhost`, single-word names (`homeserver`) and
names ending in `.local`, `.home.arpa`, `.internal` or `.ts.net`. Any other name, such as
`homeserver.fritz.box`, goes into `.env`, then restart:

```ini
NETSCOPE_ALLOWED_HOSTS=homeserver.fritz.box
```

```bash
docker compose up -d
```

A wrong name gives "NetScope does not answer to this host name" (status 400).

## 3. Status checks from the container

- **Ping works without extra rights.** NetScope pings without raw sockets, and Docker allows
  that inside every container (`net.ipv4.ping_group_range` is set per container). The
  container keeps no capabilities at all (`cap_drop: [ALL]`) and still pings.
- If ping checks fail with "Ping is not permitted for NetScope on this computer" (the host's
  `sysctl` setting does not reach the container), add this to a
  file `docker-compose.override.yml` next to `docker-compose.yml` (Compose reads it
  automatically; it is not part of the repository, so `git pull` never touches it) and run
  `docker compose up -d`:

  ```yaml
  services:
    netscope:
      sysctls:
        net.ipv4.ping_group_range: "0 2147483647"
  ```

- Checks reach your devices through Docker's normal network (NAT); host networking is not
  needed.
- **IPv6:** the container has no IPv6 address, so give devices you check an IPv4 address (or a
  hostname with one).
- **HTTPS checks with certificate checking** use the image's trusted certificates. For devices
  with certificates from your own CA, put the CA certificate (PEM) next to `docker-compose.yml`
  and point NetScope at it in `docker-compose.override.yml`:

  ```yaml
  services:
    netscope:
      volumes:
        - ./home-ca.pem:/etc/netscope/home-ca.pem:ro
      environment:
        SSL_CERT_FILE: /etc/netscope/home-ca.pem
  ```

  Verified checks then trust the certificates in that file as well as the usual public ones.
  Checks without certificate checking (the default) are not affected.

## 4. Everyday commands

| What | Command |
| --- | --- |
| Is it running (and healthy)? | `docker compose ps` |
| The log (follow it) | `docker compose logs -f netscope` |
| Stop / start / restart | `docker compose stop` / `docker compose start` / `docker compose restart` |
| Forgot the password | `docker compose exec netscope netscope reset-password` |
| Add missing default categories | `docker compose exec netscope netscope seed` |
| Size of the database | `docker compose exec netscope ls -lh /data` |

The log keeps at most 3 files of 10 MB. Add `-t` to `logs` to see when each line was written.

**Update** to the newest version (the database is migrated at startup, with a backup first):

```bash
git pull
```

```bash
docker compose up -d
```

Security fixes for the base images (Debian, Python, OpenSSL) come the same way: the Dockerfile
pins them, and a NetScope update that moves the pins rebuilds the image with them.

Old images and build files pile up after updates; remove them with `docker image prune -f` and
`docker builder prune -f`.

## 5. Backups

- **JSON export** (Settings → Backup): devices, services, links, categories, map positions
  and the status-check settings, small and readable. Not included: the password, sessions and
  the status history. Import it on the same or another NetScope (Settings → Backup).
- **Automatic copies before an import** (`/data/netscope.db.pre-import-<time>`, the newest 3
  kept): the undo for a wrong file. Restore one like a full copy below (copy it out of the
  container with `docker compose cp` first).
- **Automatic copies** of the database are written to `/data` before every migration (the
  newest 3 are kept).
- **A full copy of the database** (everything, including the admin account and the history).
  NetScope keeps running: SQLite makes a consistent copy inside the container, including
  changes not yet merged into the main file. Then copy it out and delete it there:

  ```bash
  docker compose exec netscope python -c "import os, sqlite3; os.umask(0o077); db = sqlite3.connect('/data/netscope.db'); copy = sqlite3.connect('/data/netscope-backup.db'); db.backup(copy); copy.close()"
  ```

  ```bash
  docker compose cp netscope:/data/netscope-backup.db ./netscope-backup.db
  ```

  ```bash
  docker compose exec netscope rm /data/netscope-backup.db
  ```

  The copy holds the admin's password hash: it is readable only by you (mode 600); keep it
  private. If you use `sudo` for docker, it belongs to root: `sudo chown "$USER": netscope-backup.db`
  makes it yours. A `netscope-backup.db` already in the folder is replaced without a question.
  (Copying `netscope.db` itself is only safe after a clean `docker compose stop`: after a
  crash or power loss the newest changes are still in `netscope.db-wal`.)

**Restore a full copy** (replaces everything in NetScope with the copy; here
`netscope-backup.db` in the current folder):

```bash
docker compose stop
```

```bash
docker run --rm --user 0 -v netscope_netscope-data:/data -v "$PWD":/backup:ro --entrypoint sh netscope:local -c 'rm -f /data/netscope.db-wal /data/netscope.db-shm && cp /backup/netscope-backup.db /data/netscope.db && chown 10001:10001 /data/netscope.db && chmod 600 /data/netscope.db'
```

```bash
docker compose start
```

The copy brings back the admin account and the logins as they were then: a session you ended
since ("log out other sessions") works again, and so does a password you changed since. After a
restore, use Settings → Account → "Log out other sessions", and change the password again if it
changed after the copy.

**Moving to another computer** (a homelab server or NAS later): install NetScope there as in
section 2, then restore a full copy as above, or set it up fresh and import a JSON export.
Keep the database on a local disk, not a network share (WAL mode does not work reliably there).

## 6. HTTPS with Tailscale Serve (optional)

With [Tailscale](https://tailscale.com) on this computer, Tailscale Serve can put NetScope
behind HTTPS at `https://<computer>.<tailnet>.ts.net`, reachable from your tailnet. NetScope
then only listens on this computer itself, and trusts exactly one proxy: the Docker network's
gateway, which is where Tailscale Serve's requests come from.

1. Tailscale runs on this computer (`tailscale status` lists your devices; if it does not,
   `sudo systemctl enable --now tailscaled`, then `sudo tailscale up`). In `.env`:

   ```ini
   NETSCOPE_PUBLISH=127.0.0.1:8000
   NETSCOPE_TRUSTED_PROXIES=172.30.240.1
   ```

2. Restart NetScope with the new settings:

   ```bash
   docker compose up -d
   ```

3. Turn on HTTPS for your tailnet (Tailscale admin console → **DNS** → at the bottom,
   **HTTPS Certificates** → **Enable HTTPS**), then:

   ```bash
   sudo tailscale serve --bg http://127.0.0.1:8000
   ```

4. Open the address that `tailscale serve status` prints:
   `https://<computer's Tailscale name>.<tailnet>.ts.net` (the tailnet's name alone is not an
   address; the very first open can take a minute while the certificate is issued). The
   session cookie now carries the `Secure` flag (your browser's developer tools show it under
   the site's cookies). Every device you open it from needs Tailscale connected.

For a computer that serves NetScope, turn off Tailscale's key expiry (admin console →
**Machines** → this computer → `⋯` → **Disable key expiry**); otherwise it drops off the
tailnet after some months until `sudo tailscale up`. To go back to the LAN address: delete the
two lines from `.env`, `docker compose up -d`, then `sudo tailscale serve reset`.

Why only `127.0.0.1`: if the port stayed open to the LAN, some LAN connections would also
arrive from the gateway (Docker forwards some of them, IPv6 for example), and such clients could
then fake their address and HTTPS. The fixed subnet in `docker-compose.yml`
(`172.30.240.0/24`) keeps the gateway's address the same. In this setup the LAN reaches
NetScope only through Tailscale.

If that subnet clashes with a network of yours, choose another one in
`docker-compose.override.yml` (not in `docker-compose.yml`, so `git pull` keeps working) and use
its gateway in `NETSCOPE_TRUSTED_PROXIES`:

```yaml
networks:
  default:
    ipam:
      config:
        - subnet: 172.30.250.0/24
          gateway: 172.30.250.1
```

## 7. Security notes

- **NetScope is for your home network only.** Do not forward port 8000 on your router. Remote
  access: Tailscale (section 6).
- **In the LAN setup every device on your network can reach port 8000.** NetScope closes
  connections that send no request within 10 seconds and takes at most 64 at once from one
  address and 1,024 in all, so one address cannot keep it busy. A device that uses many
  addresses still could, and connections that Docker forwards through its proxy (this computer's own browser,
  IPv6 from the LAN) share one address. The Tailscale setup keeps the port on this computer.
- **Other web apps on the same host name receive NetScope's session cookie.** Browsers send
  cookies to every port of a host name, so an app at `http://homeserver:8123` gets the cookie
  of `http://homeserver:8000` (in clear text over HTTP). Open NetScope under a name that no other
  app uses, for example its IP address while other apps use `homeserver`, or its Tailscale name.
- **Docker publishes ports past host firewalls** such as ufw. If you run one, check that port
  8000 is reachable only where you want it.
- The database (and every copy of it) holds the admin's password hash. Inside the container it
  is readable only by NetScope's user (uid 10001).
- The container runs as an unprivileged user with no capabilities, `no-new-privileges` and a
  read-only filesystem except `/data` and the temporary folders (`/tmp`, `/dev/shm`).

## 8. Troubleshooting

| Problem | Fix |
| --- | --- |
| "NetScope does not answer to this host name" | Add the name to `NETSCOPE_ALLOWED_HOSTS` in `.env` (section 2), then `docker compose up -d` |
| No setup token in the log | An admin exists already: log in, or `docker compose exec netscope netscope reset-password` |
| `docker compose ps` shows `unhealthy` or `restarting` | `docker compose logs netscope` shows why. Docker does not restart an unhealthy container by itself: if it stays unhealthy without a reason in the log, `docker compose restart` |
| "NetScope (running as user id 10001) cannot write …" | The database came from somewhere else with another owner. Give it back to NetScope's user, then `docker compose up -d`: `docker run --rm --user 0 -v netscope_netscope-data:/data --entrypoint sh netscope:local -c 'chown -R 10001:10001 /data && chmod 700 /data && chmod 600 /data/netscope.db*'` |
| Port 8000 is taken | `NETSCOPE_PUBLISH=8080` in `.env` (then open port 8080) |
| Ping checks: "Ping is not permitted…" | The `sysctls` lines in section 3 |
| A check of an IPv6 address fails | Use the device's IPv4 address (section 3) |
| "Pool overlaps with other one on this address space" when starting | Another Docker network uses `172.30.240.0/24`: choose another subnet in `docker-compose.override.yml` (section 6) |
| `git clone` or `git pull` asks for a password | Check the address: `https://github.com/123timsolotech/Netscope-open-source.git` (this public repository needs no login) |
| Startup warns that the database can be read by every user | Not expected in Docker; outside Docker run the `chmod 600` it names |
| The log says "Refused new connections: …" | More than 64 connections from one address, or 1,024 in all (section 7). A browser uses at most 6: look for a device or program at that address. In the LAN setup, this computer's own browser (and possibly IPv6 clients) share Docker's gateway address |
