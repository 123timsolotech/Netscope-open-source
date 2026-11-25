"""Login (public); logout, current user, password change and sessions (need a session)."""

from fastapi import APIRouter, Request, Response
from starlette.status import HTTP_204_NO_CONTENT

from app.api.deps import (
    ClientIp,
    CurrentSession,
    Db,
    Limiter,
    clear_session_cookie,
    replace_session_cookie,
    set_session_cookie,
)
from app.schemas.auth import CurrentUser, LoginRequest, PasswordChange, SessionsOut
from app.services import auth as auth_service

public_router = APIRouter(prefix="/auth", tags=["auth"])
router = APIRouter(prefix="/auth", tags=["auth"])


@public_router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Db,
    limiter: Limiter,
    ip: ClientIp,
) -> CurrentUser:
    new = auth_service.login(db, limiter, ip, body.username, body.password)
    set_session_cookie(request, response, new.token, new.expires_at)
    return CurrentUser(username=new.user.username)


@router.post("/logout", status_code=HTTP_204_NO_CONTENT)
def logout(current: CurrentSession, request: Request, response: Response, db: Db) -> None:
    auth_service.logout(db, current.session)
    clear_session_cookie(request, response)


@router.get("/me")
def me(current: CurrentSession) -> CurrentUser:
    return CurrentUser(username=current.user.username)


@router.post("/password")
def change_password(
    body: PasswordChange,
    current: CurrentSession,
    request: Request,
    response: Response,
    db: Db,
    limiter: Limiter,
    ip: ClientIp,
) -> CurrentUser:
    """Settings -> Account (M8). Ends every other session; this browser gets a new one."""
    new = auth_service.change_password(
        db, limiter, ip, current, body.current_password, body.new_password
    )
    replace_session_cookie(request, response, new.token, new.expires_at)
    return CurrentUser(username=new.user.username)


@router.get("/sessions")
def sessions(current: CurrentSession, db: Db) -> SessionsOut:
    return SessionsOut(other_sessions=auth_service.count_other_sessions(db, current))


@router.post("/logout-others")
def logout_others(current: CurrentSession, db: Db) -> SessionsOut:
    """Log out every other session of the admin; this one stays."""
    auth_service.end_other_sessions(db, current)
    return SessionsOut(other_sessions=0)
