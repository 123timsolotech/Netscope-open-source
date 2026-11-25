"""All API routes, mounted under /api.

Every route requires a session, except the public ones listed here: health, setup and
login (brief section 7). Add new routers to ``protected`` below.
tests/test_protected_routes.py fails if a route is reachable without a session by mistake.
"""

from fastapi import APIRouter, Depends

from app.api import (
    about,
    auth,
    backup,
    categories,
    dashboard,
    devices,
    health,
    links,
    settings,
    setup,
)
from app.api.deps import reject_cross_site, require_session

# Every /api route: block cross-site state-changing requests (see reject_cross_site).
api_router = APIRouter(prefix="/api", dependencies=[Depends(reject_cross_site)])

# Public
api_router.include_router(health.router)
api_router.include_router(setup.router)
api_router.include_router(auth.public_router)

# Session required
protected = APIRouter(dependencies=[Depends(require_session)])
protected.include_router(about.router)
protected.include_router(auth.router)
protected.include_router(backup.router)
protected.include_router(categories.router)
protected.include_router(dashboard.router)
protected.include_router(devices.router)
protected.include_router(links.router)
protected.include_router(settings.router)
api_router.include_router(protected)
