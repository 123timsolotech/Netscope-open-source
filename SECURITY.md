# Security

## Reporting a problem

Please report security problems privately, not in a public issue: on GitHub, open this
repository's **Security** tab and choose **Report a vulnerability**. Describe what you found,
how to reproduce it and which version you used (Settings in NetScope shows it). You will get an
answer as soon as possible.

Only the newest release gets security fixes.

## What NetScope is built for

NetScope is a home-network inventory for **one admin on a home network**. It is not made to be
reachable from the internet: do not forward its port on your router. For access from away, use
a VPN such as Tailscale ([`docs/deployment.md`](docs/deployment.md), section 6).

What it does to stay safe there:

- **One admin account.** The first admin is created with a one-time setup token from the log
  (or `NETSCOPE_ADMIN_PASSWORD`). Passwords have at least 20 characters and are stored as
  argon2id hashes. After 5 wrong passwords in a minute, logins from that address wait.
- **Sessions** live on the server; the cookie is `HttpOnly`, `SameSite=Lax`, and `Secure` over
  HTTPS. A session ends after 30 days without use, and 90 days after logging in at the latest.
  Only a hash of each session token is stored, so a copy of the database cannot be used to log
  in.
- **Cross-site requests are refused:** every request that changes something must be JSON (or a
  DELETE, which browsers cannot send to another site without its permission), and requests that
  browsers mark as coming from another site get `403`. NetScope sends no CORS headers.
- **DNS rebinding:** NetScope answers only to host names it can really be reached under (IP
  addresses, single-word names, `.local`, `.home.arpa`, `.internal`, `.ts.net`, and the names
  in `NETSCOPE_ALLOWED_HOSTS`).
- **Strict browser rules:** a Content-Security-Policy that runs only NetScope's own scripts and
  loads nothing from other sites, no framing, `nosniff`.
- **Limits:** request bodies of 32 KiB without a session (2 MiB with one, 10 MiB for an
  import) and 30 seconds for a body to arrive. With `python -m app` (and so in Docker; not the
  development server): 10 seconds for a request's head to arrive, at most 64 connections from
  one address (except a trusted proxy, through which everyone's requests arrive) and 1,024 in
  all.
- **Status checks** only contact the devices you entered and turned a check on for. They follow
  no redirects, use no proxy from the environment and never read an answer's body; what a
  device answers never ends up in the page as text.
- **The version** is shown only after logging in.
- **Docker:** the container runs as an unprivileged user with no capabilities,
  `no-new-privileges` and a read-only filesystem; the database and its copies are readable by
  that user only. Base images are pinned by digest and every package by its hash.

## What it does not protect against

- **Anyone who can reach the port on your network** can try to log in (slowly, because of the
  limits above) and can keep the server busy if they use many addresses at once.
- **Plain HTTP on the LAN:** the session cookie travels unencrypted. Use HTTPS (for example
  Tailscale Serve) if other people use your network.
- **Other web apps on the same host name** receive NetScope's cookie: browsers send cookies to
  every port of a host. Open NetScope under a name no other app uses.
- **Someone with access to the computer** that runs NetScope (root, or the Docker group) can
  read everything, including the database.
- **Backups:** a database copy holds the admin's password hash; keep copies private. The JSON
  export holds your devices and addresses but no password or session.
