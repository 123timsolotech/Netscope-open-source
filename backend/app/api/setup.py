"""First-run setup (public routes, brief section 7)."""

from fastapi import APIRouter, Request, Response
from starlette.status import HTTP_201_CREATED

from app.api.deps import ClientIp, Db, Limiter, Setup, set_session_cookie
from app.schemas.auth import CurrentUser, SetupRequest, SetupStatus
from app.services import auth as auth_service

router = APIRouter(prefix="/setup", tags=["auth"])


@router.get("")
def setup_status(db: Db) -> SetupStatus:
    return SetupStatus(setup_required=not auth_service.admin_exists(db))


@router.post("", status_code=HTTP_201_CREATED)
def complete_setup(
    body: SetupRequest,
    request: Request,
    response: Response,
    db: Db,
    state: Setup,
    limiter: Limiter,
    ip: ClientIp,
) -> CurrentUser:
    new = auth_service.complete_setup(
        db, state, limiter, ip, body.setup_token, body.username, body.password
    )
    set_session_cookie(request, response, new.token, new.expires_at)
    return CurrentUser(username=new.user.username)
