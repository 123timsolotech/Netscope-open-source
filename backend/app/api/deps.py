"""Shared route dependencies: database session, client info, session cookie."""

from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session as DbSession
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from app.core.db import get_db
from app.core.ratelimit import FailureRateLimiter
from app.core.timeutil import utcnow
from app.services import auth as auth_service
from app.services.auth import AuthenticatedSession, SetupState
from app.services.oui import OuiDatabase

SESSION_COOKIE = "netscope_session"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

Db = Annotated[DbSession, Depends(get_db)]


def client_ip(request: Request) -> str:
    """Client address. Behind a trusted proxy uvicorn already put the real one here."""
    return request.client.host if request.client else "unknown"


def get_limiter(request: Request) -> FailureRateLimiter:
    limiter: FailureRateLimiter = request.app.state.limiter
    return limiter


def get_setup_state(request: Request) -> SetupState:
    state: SetupState = request.app.state.setup
    return state


def get_oui(request: Request) -> OuiDatabase:
    """The MAC vendor list, loaded once at startup."""
    oui: OuiDatabase = request.app.state.oui
    return oui


ClientIp = Annotated[str, Depends(client_ip)]
Oui = Annotated[OuiDatabase, Depends(get_oui)]
Limiter = Annotated[FailureRateLimiter, Depends(get_limiter)]
Setup = Annotated[SetupState, Depends(get_setup_state)]


def set_session_cookie(
    request: Request, response: Response, token: str, expires_at: datetime
) -> None:
    """HttpOnly, SameSite=Lax, and Secure when the request came over HTTPS (brief section 7)."""
    max_age = max(0, int((expires_at - utcnow()).total_seconds()))
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        path="/",
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )


def replace_session_cookie(
    request: Request, response: Response, token: str, expires_at: datetime
) -> None:
    """A new session for this browser (password change, M8): drop the old session's cookie
    that require_session already added, then set the new one."""
    if "set-cookie" in response.headers:
        del response.headers["set-cookie"]
    set_session_cookie(request, response, token, expires_at)


def clear_session_cookie(request: Request, response: Response) -> None:
    # Only the deletion: drop the refreshed cookie require_session already added.
    if "set-cookie" in response.headers:
        del response.headers["set-cookie"]
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )


def require_session(request: Request, response: Response, db: Db) -> AuthenticatedSession:
    """Every /api route except health, setup and login depends on this (brief section 7)."""
    token = request.cookies.get(SESSION_COOKIE)
    auth = auth_service.authenticate(db, token)
    if auth is None:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    if token is not None:
        # Sent with every authenticated answer, Max-Age from the stored expiry (which is
        # renewed at most once a day). When a route ends in an error FastAPI drops this
        # response, and a renewal would not reach the browser; the next successful answer
        # then repairs the cookie (security audit, M2).
        set_session_cookie(request, response, token, auth.session.expires_at)
    return auth


CurrentSession = Annotated[AuthenticatedSession, Depends(require_session)]


def reject_cross_site(request: Request) -> None:
    """Block state-changing requests that a browser marks as coming from another site.

    SameSite=Lax ignores ports, so another web app on the same host (for example
    http://thinkpad:8123) counts as "same-site" and could send the cookie. Browsers label
    every request with Sec-Fetch-Site; only "same-origin" and "none" (typed URL, bookmark)
    are let through. Requests without the header (curl, scripts) are not browsers and carry
    no ambient cookie, so they pass.
    """
    if request.method in UNSAFE_METHODS and request.headers.get("sec-fetch-site") in {
        "cross-site",
        "same-site",
    }:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Cross-site request blocked.")
