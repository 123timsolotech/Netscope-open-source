"""App factory: settings, database, migrations at startup, API routes and the frontend."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.errors import register_exception_handlers
from app.api.guards import RequestGuardMiddleware
from app.api.router import api_router
from app.core.config import Settings, get_settings, unknown_environment_variables
from app.core.db import create_db_engine, create_session_factory
from app.core.headers import SecurityHeadersMiddleware
from app.core.hosts import HostAllowlistMiddleware
from app.core.logs import configure_logging
from app.core.migrate import database_open_to_others, migrate_database
from app.core.ratelimit import FailureRateLimiter
from app.monitor.checks import Checker, run_check
from app.monitor.scheduler import Monitor
from app.services import auth as auth_service
from app.services.oui import load_bundled_oui
from app.spa import register_spa

logger = logging.getLogger("netscope")


def create_app(
    settings: Settings | None = None,
    *,
    run_monitor: bool = True,
    checker: Checker | None = None,
) -> FastAPI:
    """Build the app. Nothing touches the disk until startup (the lifespan).

    The status monitor starts with the app. Tests turn it off (``run_monitor=False``), or give
    it a fake ``checker``: they never contact real devices.
    """
    settings = settings or get_settings()
    database_file = settings.database_file

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        logger.info("NetScope %s starting. Database: %s", __version__, database_file)
        for name in unknown_environment_variables():
            logger.warning("Ignoring unknown setting %s (a typo?).", name)
        migrate_database(database_file)
        if database_open_to_others(database_file):
            logger.warning(
                "%s can be read or changed by every user of this computer, and it holds the "
                "admin's password hash. To fix: chmod 600 %s",
                database_file,
                database_file,
            )

        engine = create_db_engine(database_file)
        session_factory = create_session_factory(engine)
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.oui = load_bundled_oui()
        monitor: Monitor | None = None
        try:
            with session_factory() as db:
                app.state.setup = auth_service.bootstrap(db, settings)
            if run_monitor:
                # Looked up now, not at import: the test fixtures replace run_check.
                monitor = Monitor(session_factory, checker or run_check)
                monitor.start()
            app.state.monitor = monitor
            yield
        finally:
            if monitor is not None:
                await monitor.stop()
            engine.dispose()

    # No /docs or /redoc: they load scripts and fonts from public CDNs on NetScope's own
    # origin (with the admin's session) and break "works offline" (security audit, M2). No
    # /openapi.json either: it showed every route and the version without a login, and nothing
    # needs it (final security audit, M8). The schema still comes from app.openapi()
    # (scripts/export_openapi.py, the tests).
    app = FastAPI(
        title="NetScope",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.limiter = FailureRateLimiter()
    # Starlette runs the last added middleware first: headers go on every response,
    # including the body limit's 413.
    app.add_middleware(RequestGuardMiddleware)
    app.add_middleware(HostAllowlistMiddleware, extra_hosts=settings.allowed_host_list)
    app.add_middleware(SecurityHeadersMiddleware)
    register_exception_handlers(app)
    app.include_router(api_router)
    # Registered last: its catch-all route must not shadow the API.
    register_spa(app, settings.frontend_dist)
    return app


app = create_app()
