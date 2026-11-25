# NetScope: one container for the home server (brief section 11; docs/deployment.md).
#
# Three stages:
#   1. frontend: build the web interface with Node 24.
#   2. backend:  install the backend's locked dependencies with uv into /app/.venv.
#   3. runtime:  Python, the venv, the app, its migrations, the MAC vendor list and the built
#                frontend. No Node, no uv, no compilers.
#
# Base images are the official Docker Hub images, pinned by digest (the tag is for reading).
# To update them, look up the current digest of each tag, e.g.
#   docker buildx imagetools inspect python:3.13-slim-trixie
# and replace both lines that use it (decision M8.2).

# --- 1. Frontend -------------------------------------------------------------------------------
FROM node:24-trixie-slim@sha256:af02d57b57719b9657a45199a79264a9437940cd55b3c7b3fc99615654f124a0 AS frontend

WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2. Backend dependencies -------------------------------------------------------------------
FROM python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS backend

# uv from PyPI, the version the project uses (the ghcr.io uv image is not reachable from every
# build machine; decision M8.2), checked against the hashes PyPI publishes for its wheels, like
# every other package (final security audit, M8). To update it: the new version and the sha256
# of each of its three wheels below (manylinux x86_64, manylinux_2_17 aarch64 and
# manylinux_2_28 aarch64; pip takes the 2_28 one on arm64) from
# https://pypi.org/project/uv/<version>/#files
RUN echo "uv==0.11.32" \
        "--hash=sha256:3da76cd4e2697de30928b8a8524bd39183ac1e08cb7e72833807c022b7cba6c4" \
        "--hash=sha256:125c142363d0842c8506a057da56bae182e2aa3957344f57dd9ef20ea10f06b0" \
        "--hash=sha256:be0799f1ad70c755d10de5aaf46af94199d4f16a992f90278f2662350cd3f4fe" \
        > /tmp/uv-requirements.txt \
    && pip install --no-cache-dir --disable-pip-version-check --root-user-action=ignore \
        --require-hashes --only-binary :all: -r /tmp/uv-requirements.txt \
    && rm /tmp/uv-requirements.txt

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app
# Dependencies first, so a code change does not reinstall them.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
# The app keeps the repository layout (/app/app, /app/migrations, /app/alembic.ini): it finds
# its migrations next to its own source (decision M1.14). Installed as an editable project, so
# the `netscope` command exists and runs this code.
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/app ./app
RUN uv sync --locked --no-dev \
    && .venv/bin/python -m compileall -q app migrations

# --- 3. Runtime --------------------------------------------------------------------------------
FROM python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS runtime

# An unprivileged user. /data holds the database; a new named volume takes this owner and
# mode, so the database stays private (brief section 7). No setuid or setgid programs (su,
# mount, passwd from the base image): no-new-privileges already makes them harmless, this
# removes them as a second line of defense (final security audit, M8).
RUN groupadd --gid 10001 netscope \
    && useradd --uid 10001 --gid netscope --no-create-home --home-dir /nonexistent \
        --shell /usr/sbin/nologin netscope \
    && install -d -o netscope -g netscope -m 0700 /data \
    && find / -xdev -type f -perm /6000 -exec chmod ug-s {} +

COPY --from=backend /app /app
COPY --from=frontend /src/frontend/dist /app/frontend/dist

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NETSCOPE_HOST=0.0.0.0 \
    NETSCOPE_PORT=8000 \
    NETSCOPE_DATABASE_PATH=/data/netscope.db \
    NETSCOPE_FRONTEND_DIST=/app/frontend/dist

WORKDIR /app
USER netscope
VOLUME ["/data"]
EXPOSE 8000

# No curl in the image: Python asks the health route (no proxy, IP host name).
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request as u; o = u.build_opener(u.ProxyHandler({})); sys.exit(0 if o.open('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"]

# Exactly one worker: the status monitor runs inside the app process (brief section 4).
CMD ["python", "-m", "app"]
