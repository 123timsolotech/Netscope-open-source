"""Checks that run before a request body is read (security audit, M2).

FastAPI reads the whole body into memory before any dependency runs, the session check
included, and uvicorn has no body limit or body timeout. One 300 MB request from any device on
the LAN took the app to about 1 GB of memory without logging in, and stalled uploads stayed
open for good. So, in this order:

1. **JSON only.** Every ``/api`` request that may carry a body (anything but GET, HEAD,
   OPTIONS and DELETE) needs ``Content-Type: application/json`` exactly, logout included.
   A page on another site can send that type only after a CORS preflight, which fails (no
   CORS headers), so this blocks cross-site requests even over plain HTTP, where browsers do
   not send ``Sec-Fetch-Site`` (decision M2.12 assumed they always do). DELETE is exempt:
   cross-site DELETE needs a preflight anyway.
2. **Size.** At most 32 KiB, or 2 MiB for a request with a live session (the largest valid
   device save is about 1.7 MB), or 10 MiB for ``POST /api/import`` with a live session (an
   export file, owner decision M8; ``IMPORT_BODY_LIMIT``). Login and setup always get 32 KiB
   (their largest valid body is about 15 KB). Anonymous clients therefore cannot make the app
   buffer much, however many connections they open. The session lookup only runs for bodies
   over 32 KiB and within the route's session limit.
3. **Time.** The body must arrive within 30 seconds (408 otherwise), so stalled uploads do
   not hold memory and connections.
"""

import json
from collections.abc import Iterable

import anyio
from fastapi import HTTPException
from starlette.requests import HTTPConnection
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_408_REQUEST_TIMEOUT,
    HTTP_413_CONTENT_TOO_LARGE,
    HTTP_415_UNSUPPORTED_MEDIA_TYPE,
)
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.schemas.backup import IMPORT_BODY_LIMIT
from app.services import auth as auth_service

SESSION_COOKIE = "netscope_session"  # same as app.api.deps (not imported: no cycle)
ANONYMOUS_BODY_LIMIT = 32 * 1024
SESSION_BODY_LIMIT = 2 * 1024 * 1024
BODY_READ_SECONDS = 30.0
PUBLIC_PREFIXES = ("/api/auth/login", "/api/setup")
# The only route with a larger limit (matched exactly).
IMPORT_ROUTE = ("POST", "/api/import")
METHODS_WITHOUT_JSON_RULE = frozenset({"GET", "HEAD", "OPTIONS", "DELETE"})
JSON_ONLY = "Send JSON (Content-Type: application/json)."
TOO_SLOW = "The request body took too long to arrive."


def too_large(limit: int) -> str:
    size = f"{limit // (1024 * 1024)} MiB" if limit >= 1024 * 1024 else f"{limit // 1024} KiB"
    return f"Request body too large (at most {size})."


def session_body_limit(method: str, path: str) -> int:
    """The limit for a request with a live session."""
    return IMPORT_BODY_LIMIT if (method, path) == IMPORT_ROUTE else SESSION_BODY_LIMIT


def is_api(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")


def media_type(headers: Iterable[tuple[bytes, bytes]]) -> str | None:
    """The request's media type, lower case, without parameters. None if absent or sent more
    than once. Parsed, not searched: "text/plain; application/json" is text/plain."""
    values = [value for name, value in headers if name == b"content-type"]
    if len(values) != 1:
        return None
    return values[0].decode("latin-1").split(";", 1)[0].strip().lower()


class RequestGuardMiddleware:
    """Pure ASGI middleware; answers 415, 413, 408 or 400 without reading the body."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]
        if (
            is_api(path)
            and scope["method"] not in METHODS_WITHOUT_JSON_RULE
            and media_type(scope["headers"]) != "application/json"
        ):
            await reject(send, HTTP_415_UNSUPPORTED_MEDIA_TYPE, JSON_ONLY)
            return

        may_grow = not path.startswith(PUBLIC_PREFIXES)
        session_limit = session_body_limit(scope["method"], path)
        limit = ANONYMOUS_BODY_LIMIT
        declared = content_length(scope["headers"])
        if declared == -1:
            await reject(send, HTTP_400_BAD_REQUEST, "Invalid Content-Length header.")
            return
        if declared is not None and declared > limit:
            if may_grow and declared <= session_limit and await has_live_session(scope):
                limit = session_limit
            else:
                over_all = may_grow and declared > session_limit
                shown = session_limit if over_all else ANONYMOUS_BODY_LIMIT
                await reject(send, HTTP_413_CONTENT_TOO_LARGE, too_large(shown))
                return

        received = 0
        body_done = False
        deadline: float | None = None

        async def guarded_receive() -> Message:
            nonlocal received, body_done, deadline, limit
            if body_done:  # later calls only wait for a disconnect: no deadline
                return await receive()
            if deadline is None:
                deadline = anyio.current_time() + BODY_READ_SECONDS
            try:
                with anyio.fail_after(max(deadline - anyio.current_time(), 0.001)):
                    message = await receive()
            except TimeoutError:
                # FastAPI re-raises HTTPExceptions from body reading; its handler answers.
                raise HTTPException(status_code=HTTP_408_REQUEST_TIMEOUT, detail=TOO_SLOW) from None
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                body_done = not message.get("more_body", False)
                if received > limit:
                    if limit == ANONYMOUS_BODY_LIMIT and may_grow and await has_live_session(scope):
                        limit = session_limit
                    if received > limit:
                        raise HTTPException(
                            status_code=HTTP_413_CONTENT_TOO_LARGE, detail=too_large(limit)
                        )
            else:
                body_done = True
            return message

        await self.app(scope, guarded_receive, send)


async def has_live_session(scope: Scope) -> bool:
    """Whether the request's session cookie is valid (checked in a worker thread)."""
    token = HTTPConnection(scope).cookies.get(SESSION_COOKIE)
    if not token:
        return False
    factory = scope["app"].state.session_factory

    def check() -> bool:
        with factory() as db:
            return auth_service.session_is_live(db, token)

    return await anyio.to_thread.run_sync(check)


def content_length(headers: Iterable[tuple[bytes, bytes]]) -> int | None:
    """The declared length, None if absent, -1 if malformed or sent twice."""
    values = [value for name, value in headers if name == b"content-length"]
    if not values:
        return None
    if len(values) > 1 or not values[0].isdigit():
        return -1
    return int(values[0])


async def reject(send: Send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
