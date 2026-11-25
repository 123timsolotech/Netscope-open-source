# NetScope user guide

Everything you do with NetScope day to day: opening it, your devices and their services,
categories, the map, status checks, the dashboard, your account, backups, and the Docker
commands on the computer it runs on (called **the server** below). For NetScope 0.1.0.

- Installing it: [`deployment.md`](deployment.md).

Commands run on the server, in the folder NetScope was cloned into:

```bash
cd ~/netscope
```

If your user is not in the `docker` group, put `sudo` in front of every `docker` command.

**Your routine, in short:**

- **Every day:** nothing is required. NetScope checks your devices by itself while the
  server is on. Open it when you want to know what is up or down: the dashboard shows it.
- **Something is down:** dashboard → **Down now** for the reason, then the map to see what it
  hangs off (section 7).
- **Something at home changes** (a new device, a new address, a device gone): change it in
  NetScope the same day, so the list and the checks stay right.
- **After bigger changes, or once a week:** **Settings → Backup → Download export**; keep the
  file on another computer (section 11).
- **When there is a new version:** update on the server (section 12).

## 1. Open NetScope

**On your home network** (the default install): `http://<the server's IP address>:8000`. On
the server, `ip -4 -br addr` shows the address (on the `wl…` or `en…` line). A name such as
`http://homeserver:8000` works only if your router knows that name.

**With Tailscale Serve** (HTTPS, also away from home; `deployment.md`, section 6), the address
is the server's Tailscale name plus your tailnet's name:

```text
https://<the server's Tailscale name>.<your tailnet>.ts.net
```

On the server, `tailscale serve status` prints it. The tailnet's name alone
(`<your tailnet>.ts.net`) is not an address. It works the same at home and away, on every
device of yours that runs Tailscale:

- **Tailscale must be connected on the device you open it from.** Without it the page says
  "This site can't be reached".
- **The server must be on and online, with Tailscale running.** When it is off or asleep the
  page does not load and no checks run; when it is back, NetScope continues by itself (for
  about a minute the signs may say "No recent check").
- Away from home the page works, but the checks still run from the server: if the server is a
  laptop you take somewhere else, your home devices show Down. That is expected.
- In this setup port 8000 is closed to your home network on purpose:
  `http://<IP address>:8000` no longer works.

- Bookmark it. On a phone, "Add to Home screen" puts a shortcut on the home screen (it opens
  in the browser).
- **"NetScope does not answer to this host name":** the name has dots and is not a `.local`,
  `.home.arpa`, `.internal` or `.ts.net` name. Add it to `NETSCOPE_ALLOWED_HOSTS` in `.env`
  (section 12).
- **"Cannot reach NetScope"** or the page does not load: section 13.
- Never forward port 8000 on your router; from outside, use Tailscale.

## 2. First start (once)

1. Read the one-time setup token from the log (if it shows several, use the **last** one; copy
   and paste it: it is case-sensitive):

   ```bash
   docker compose logs netscope
   ```

2. Open NetScope. The **Set up NetScope** page asks for the token, a username (3–64 letters,
   digits, `.`, `_`, `-`) and a password of at least 20 characters, twice.
3. You are logged in and land on the dashboard. The 12 default categories (Router, Switch,
   Server, NAS, Access point, PC, Phone, IoT, Printer, Camera, TV / Media, Other) are ready.
4. Add your real devices, starting with the router (section 4). If you tried the demo devices
   (`seed --demo`), start over first (`docker compose down -v`, then `docker compose up -d`, and
   set up again): the demo devices are made up, and their addresses may belong to real devices
   of yours.
5. Then turn on the router's check (section 8, Ping), add the rest of your devices, link them
   on the map (section 7), and download a first export (section 11).

The token changes every time NetScope restarts until setup is done; then it stops working.

## 3. Log in and out

- Opening any page without a session shows **Log in**, then takes you back to that page.
- Usernames ignore case. After 5 wrong passwords within a minute, the page counts down until
  you can try again.
- A session ends after 30 days without use, and 90 days after logging in at the latest.
  "Your session ended" means: log in again.
- **Log out** is at the bottom of the sidebar (on a phone: the menu button at the top right).
- Forgot the password? Section 12, "Forgot the password".

## 4. Devices

**Add one:** **Devices** → **Add device**. Only the name is required, and names are unique
(ignoring case). The form has five parts:

| Part | What goes in |
| --- | --- |
| Basics | name, category, role (for example "Plex" or "DNS"), location |
| Addresses | IP address, hostname, MAC address |
| Services | the ports it serves (section 5) |
| Notes | description |
| Status check | whether and how NetScope checks it (section 8), collapsed |

- The **vendor** comes from the MAC when you save (an offline list; nothing is looked up
  online). A phone's private Wi-Fi address shows "Randomized (private) MAC".
- **Saved. Please check:** another device has the same IP or MAC. The device is saved and the
  form stays open; the amber box at the top names the other device. Two entries that really
  share an address are fine (better: one device with several services); the box then shows
  after every save.
- Problems show next to their field; anything without a field shows in a box at the top.
- **Edit:** click the name in the list. **Delete:** in the form, or the `⋯` menu in the list.
  Deleting asks first, and also deletes the device's services, links and status history.
- Leaving a form with unsaved changes asks first.

**Find one:** the search box looks at name, hostname, IP, MAC (with or without `:` or `-`, so
`b827eb` works), vendor, role, location, description, category and each service's name, note and
port. Every word must match (`plex office`). **All categories** filters by category (also "No
category"). Click **Status**, **Name**, **Category** or **IP address** to sort, again to
reverse (on a phone: the arrows at the top left sort by status; there is no Category column).
Search, filter and sort stay in the address bar, so a bookmark keeps them.

**Tip:** give every device you check a fixed address (a DHCP reservation in your router).
NetScope checks the address you entered; if the router hands the device a new one, the check
goes to the old one.

## 5. Services

A service is a note of what a device offers: port, TCP or UDP, a name, an optional note
("22/tcp SSH, key only"; "8123/tcp Home Assistant"). One row each; **Add service** adds a row,
the bin icon removes one.

- 53/tcp and 53/udp on one device is fine; the same port and protocol twice is not.
- Services are for your records and the search. NetScope does not check them: only the
  device's status check (section 8) contacts the device.

## 6. Categories

**Settings → Categories:** each category with its icon, color and number of devices (click the
number to see them). **Add category** or the pencil: a name, a color (presets or "Other
color") and an icon. Deleting a category keeps its devices; they get no category (the dialog
says how many).

## 7. The map (Topology)

**Topology** shows every device as a box (category icon, name, IP address or hostname) and
every link as a line: solid = Ethernet, dashed = Wi-Fi, dotted = VPN, dash-dot = other.

- **Move:** drag a box. It snaps to a 20 px grid and is saved when you let go. Shift + drag
  across the map (or Ctrl/Cmd + click) selects several. Keyboard: Tab to a box, Enter, arrow
  keys (Shift: faster), Escape. Moving is not an edit.
- **New devices** appear at the first free spot of the grid.
- **Details:** click or tap a box. The panel (beside the map; below it on a phone) shows its
  status, addresses, services and links. **Edit device** opens the form and comes back to the
  map. Close with ✕ or Escape.
- **Link two devices:** drag from the dot on a box's right edge onto another box, or use **Add
  link** (above the map or in the details panel). Choose the type and an optional label
  ("LAN 1", "port 4"), then confirm. A device cannot be linked to itself or twice to the same
  device.
- **Change or delete a link:** click the line or its label, or use the pencil or bin in the
  details panel. Deleting asks first.
- **Zoom and pan:** mouse wheel or pinch, drag the background; the buttons at the bottom left
  zoom and fit everything. A reload fits the map to all devices.
- A down device has a red border, so it shows when zoomed out.

Typical use: when something is down, open the map and follow its links. If the switch it hangs
off is red too, look at the switch first.

## 8. Status checks

NetScope contacts only the devices whose check you turn on. It never scans your network.

**Turn one on:** open the device → **Status check** → choose the **Check type**, switch on **Check
turned on**, fill in what the type needs, **Save changes** (**Add device** for a new one). Within about 10 seconds the list
shows the result.

| Check type | Up when | Also needs |
| --- | --- | --- |
| Ping (ICMP) | the device answers one ping | nothing |
| TCP port | a connection to the port opens | the port |
| HTTP(S) request | the page answers 200–399, or 401/403 (a login page) | optional: scheme (`http` by default, or `https`), port (default 80 or 443), path (default `/`) |

Every check needs the device's IP address or hostname: it uses the IP address if the device has
one, otherwise the hostname. HTTPS checks accept any certificate unless you turn on **Verify the
HTTPS certificate** (home devices mostly use self-signed ones).

**Which check for which device:**

| Device | Check |
| --- | --- |
| Router, access point, managed switch | Ping |
| Raspberry Pi, Linux server | Ping, or TCP port 22 (SSH) to see that the system itself answers |
| NAS | Ping, or HTTP(S) on its web page's port (Synology: 5000 or 5001), or TCP port 445 (file shares); SSH is often off on a NAS |
| A web app (Home Assistant on 8123, Plex on 32400 with path `/identity`) | HTTP(S) on its port |
| Printer, camera | Ping, or HTTP on port 80 (its web page) |
| Smart TV | Leave it off, or accept Down while it is in standby |
| Windows PC | Windows blocks ping by default: TCP port 445 if file sharing is on (3389 if Remote Desktop is on), or allow ping in its firewall. A PC that sleeps or is switched off shows Down |
| Phone, tablet, laptop | Leave it off: they sleep, leave the house and drop off Wi-Fi, so they would show Down |
| Unmanaged switch | It has no address: no check; it still belongs on the map |
| The server itself | No check: if it is down, NetScope is too |

In Docker, checks need an IPv4 address (or a hostname with one): the container has no IPv6.

**The signs** (in the list, on the map, in the form and on the dashboard):

| Sign | Words | Meaning |
| --- | --- | --- |
| green ✓ | Up · 3 ms | The latest check worked; or fewer than **Down after** checks have failed since, then it adds "Last check failed: …" |
| red ✕ | Down + the reason | **Down after** checks in a row failed (2 by default) |
| gray dashed ring | Waiting for check | Just turned on or changed: no check has worked yet, and fewer than **Down after** have failed |
| gray clock | No recent check | The latest result is older than about three intervals |
| none | Not checked | The check is off |

Hover a sign (or a box on the map) for the whole sentence, for example "Down: Connection
refused on port 22. Last check 18:42:10." On a phone (no hover, and the list shows only the
sign): the dashboard's **Down now** lists each reason, or tap the box on the map, or open the
device (its **Status check** part shows the current status). Reasons you may see: "Timed out after 5 s",
"Connection refused on port 22", "HTTP 503 (Service Unavailable)", "Ping is not permitted…".

**How fast:** with the defaults (every 30 s, 5 s timeout, down after 2 failures) a device that
goes away turns red after about 35–65 seconds, on your screen within about 1.5 minutes (pages
reload every 30 seconds). One successful check turns it green again. Changing a device's check
starts its status afresh ("Waiting for check"); it is checked within a few seconds.

**Settings → Status checks:**

| Setting | Range | Default |
| --- | --- | --- |
| Check every | 10–3600 seconds | 30 |
| Timeout per check | 1–30 seconds, at most half the interval | 5 |
| Down after | 1–10 failed checks in a row | 2 |
| Keep history for | 1–30 days | 7 |

**Save settings** stores only what you changed; NetScope uses it within a few seconds.
**Discard changes** puts the saved values back. Every check is stored for the history: about
5 MB per checked device and week at a 30-second interval (the page shows its estimate). Older
checks are deleted every hour. NetScope does not show the history yet (charts come later), and it sends no alerts: look at
the dashboard.

**When did it go down?** The log notes every change from up to down and back:

```bash
docker compose logs -t netscope | grep -E " is down| is up again"
```

## 9. Dashboard

The first page after logging in. It reloads every 30 seconds.

- **The summary** under the title ("8 of 15 devices checked: 6 up, 1 down") and the totals of
  devices, links and services.
- **Search:** type and press Enter to open the device list with that search.
- **Status:** every status with its count; a count opens the device list sorted by status,
  down first.
- **Down now:** each device that is down, with the reason and the time of the last check;
  click a name for its form (back returns to the dashboard).
- **Devices by category:** most first, then "No category"; a row opens the filtered list.
- **Recently edited:** the 5 devices added or edited last. Moving one on the map, a status
  result or saving without changes is not an edit.
- **An amber box** "No status check has finished for … Is NetScope's monitor running? See the
  log." means the checks have stopped: look at the log, then restart (section 12).

## 10. Your account

**Settings → Account:**

- **Change password:** the current one, then the new one twice (at least 20 characters). Every
  other browser and device is logged out; this one stays logged in.
- **Sessions:** how many other browsers or devices are logged in, and **Log out other
  sessions** (for example after using a friend's laptop).
- The NetScope version is at the bottom of every Settings page.

## 11. Backups and restore

Two kinds of backup:

| | JSON export | Full database copy |
| --- | --- | --- |
| Made in | Settings → Backup | the server's terminal |
| Holds | devices with services, links, categories, map positions, the status-check settings you changed | everything: also the admin account, sessions and the status history |
| Restored with | Settings → Backup → import | the restore commands below |
| Good for | regular backups, moving to another NetScope | a complete copy of this install |

**Export regularly** (after bigger changes) and keep the file somewhere other than the
server: **Settings → Backup → Download export** saves `netscope-export-<date>.json`.

**Import a file:** **Settings → Backup**, choose the file and a mode, then **Check file**.
NetScope checks the whole file and shows what will happen (what it deletes, adds and updates,
and how many devices have status checks on), or lists the problems with their place. Nothing is
written until you click **Replace everything** (Replace all; it asks once more) or **Import**
(Merge).

- **Replace all** (the default): deletes every device, category and link (with the status
  history) and adds what is in the file. The status-check settings become the file's
  (settings the file leaves out go back to their defaults). Your login stays.
- **Merge by device name:** adds what is in the file; devices and categories with the same
  name are updated from it; nothing is deleted; your settings stay.
- Before every import NetScope copies its database (the newest 3 copies are kept): the undo
  for a wrong file (below).
- Imported devices whose check is on start at "Waiting for check" and are checked right away.
- Files up to 10 MiB, UTF-8 (as NetScope writes them).

**A full database copy** (NetScope keeps running). Make the copy inside the container:

```bash
docker compose exec netscope python -c "import os, sqlite3; os.umask(0o077); db = sqlite3.connect('/data/netscope.db'); copy = sqlite3.connect('/data/netscope-backup.db'); db.backup(copy); copy.close()"
```

Copy it out (a `netscope-backup.db` already in this folder is replaced without a question:
rename an older one first):

```bash
docker compose cp netscope:/data/netscope-backup.db ./netscope-backup.db
```

Delete it inside the container:

```bash
docker compose exec netscope rm /data/netscope-backup.db
```

The copy holds the admin's password hash. It is readable only by you (mode 600); keep it
private. If you use `sudo` for docker, it belongs to root; this makes it yours:

```bash
sudo chown "$USER": netscope-backup.db
```

**Restore a full copy** (replaces everything in NetScope with `netscope-backup.db` from the
current folder). Stop NetScope:

```bash
docker compose stop
```

Put the copy in place:

```bash
docker run --rm --user 0 -v netscope_netscope-data:/data -v "$PWD":/backup:ro --entrypoint sh netscope:local -c 'rm -f /data/netscope.db-wal /data/netscope.db-shm && cp /backup/netscope-backup.db /data/netscope.db && chown 10001:10001 /data/netscope.db && chmod 600 /data/netscope.db'
```

Start it again:

```bash
docker compose start
```

A copy brings back NetScope as it was then, the password and the logins included: a phone you
logged out since (Settings → Account) is logged in again, and an older password works again.
After a restore, open Settings → Account and log out other sessions; change the password
again if you changed it after the copy was made.

**Undo a wrong import:** list the copies (`netscope.db.pre-import-<time>`, in UTC):

```bash
docker compose exec netscope ls -l /data
```

The next command replaces any `netscope-backup.db` in this folder. If you have one (for
example an earlier full copy), rename it first:

```bash
mv netscope-backup.db netscope-backup-old.db
```

Copy out the one made just before the import, under the name the restore expects (put in its
real name), then restore it as above (the password and the logins also go back to that
moment):

```bash
docker compose cp netscope:/data/netscope.db.pre-import-<time> ./netscope-backup.db
```

## 12. On the server (Docker)

| What | Command |
| --- | --- |
| Is it running and healthy? | `docker compose ps` (STATUS says `healthy`) |
| The log | `docker compose logs netscope` |
| Follow the log | `docker compose logs -f netscope` (Ctrl+C stops following) |
| The last 50 lines, with times | `docker compose logs -t --tail 50 netscope` |
| Restart | `docker compose restart` |
| Stop / start | `docker compose stop` / `docker compose start` |
| Size of the database | `docker compose exec netscope ls -lh /data` |
| Add missing default categories | `docker compose exec netscope netscope seed` |

NetScope starts by itself after a crash, a reboot or a Docker update (not after you stopped it
with `docker compose stop`: then `docker compose start`). While the server is off or asleep,
NetScope is too; nothing is lost, and the checks continue when it is back.

**Update to the newest version** (the database is migrated at startup, with a copy first):

```bash
git pull
```

```bash
docker compose up -d
```

Old images and build files pile up after updates; remove them now and then:

```bash
docker image prune -f
```

```bash
docker builder prune -f
```

**Forgot the password** (asks for the new one twice and logs out every session):

```bash
docker compose exec netscope netscope reset-password
```

**Changed `.env`** (for example `NETSCOPE_ALLOWED_HOSTS`): apply it with `up -d`, not
`restart` (only `up -d` reads `.env`):

```bash
docker compose up -d
```

**Tailscale on the server:**

| What | Command |
| --- | --- |
| Is Tailscale connected? Which of your devices are online? | `tailscale status` |
| NetScope's address | `tailscale serve status` |
| Start Tailscale again (after it was stopped) | `sudo systemctl enable --now tailscaled`, then `sudo tailscale up` |

- Tailscale keeps the Serve setting through reboots and renews the HTTPS certificate by itself.
- **Key expiry:** Tailscale logs a device out after some months (the admin console shows "Key
  expiry"); then the address stops working until you run `sudo tailscale up` on the
  server. For the server, turn it off: Tailscale admin console → **Machines** → the
  server → `⋯` → **Disable key expiry**.
- **Back to the home-network address** (without Tailscale): delete the lines
  `NETSCOPE_PUBLISH` and `NETSCOPE_TRUSTED_PROXIES` from `.env`, run `docker compose up -d`,
  then `sudo tailscale serve reset`.

## 13. When something is wrong

| What you see | What to do |
| --- | --- |
| "This site can't be reached" | Is Tailscale connected on this phone or computer? Is the server on? Did you use the full address (section 1)? On the server: `tailscale status` and `tailscale serve status` (section 12) |
| The page does not load at all | `docker compose ps`; if NetScope is not running, `docker compose up -d`, then `docker compose logs netscope` |
| Every device is Down at once | Is the server at home and on your network? Is the router up? |
| "NetScope does not answer to this host name" | Add the name to `NETSCOPE_ALLOWED_HOSTS` in `.env`, then `docker compose up -d` |
| No setup token in the log | The admin exists already: log in, or reset the password (section 12) |
| A device is Down but it is on | Is its IP still right (section 4, tip)? Does it answer ping at all? Try a TCP or HTTP check |
| "Ping is not permitted…" | The message mentions the README; in Docker the fix is `deployment.md`, section 3 (one `sysctls` entry) |
| "No recent check" everywhere, or the amber box on the dashboard | `docker compose logs netscope`, then `docker compose restart` |
| "NetScope is busy. Try again in a few seconds." | A large import holds the database: wait, then try again |
| The log says "Refused new connections: … per address" | Something at that address opened more than 64 connections at once (NetScope refuses the rest). Your own browsers never get there: look for a misbehaving device or program at that address |
| `docker compose ps` shows `unhealthy` | `docker compose logs netscope` says why; Docker does not restart it by itself: `docker compose restart` |
| Anything else | `deployment.md`, section 8 (troubleshooting) |
