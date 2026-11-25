"""Security headers on every response (security audit, M2).

- ``X-Frame-Options`` / ``frame-ancestors``: no page may show NetScope in a frame. Browsers
  send the session cookie to other web apps on the same host (cookies ignore ports), so a page
  on another port could otherwise frame the logged-in UI and trick clicks (clickjacking).
- ``nosniff``: files are only used as the type they are served as.
- ``Referrer-Policy: same-origin``: links to a device's own web interface do not send the
  NetScope URL along.
- ``Content-Security-Policy`` (M4): the built frontend loads only its own files. Scripts come
  from NetScope only (no inline scripts, no ``eval``), so injected markup cannot run code.
  Styles also allow inline ``<style>`` elements and attributes: Sonner and Radix insert them at
  runtime, and the map (M5) positions nodes with inline styles. Nothing loads from the
  internet, which also keeps NetScope working offline. The Vite dev server (port 5173) serves
  its own pages without this header, so hot reload keeps working.
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self'",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    )
)

SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
}


class SecurityHeadersMiddleware:
    """Pure ASGI middleware (no buffering): adds the headers unless a response set them."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
            await send(message)

        await self.app(scope, receive, send_with_headers)
