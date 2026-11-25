"""Run NetScope: ``python -m app``.

Always exactly one worker: the status monitor (M6) runs inside the app process, and more
workers would start more than one monitor (brief section 4). Connections are guarded
(``app/core/server.py``: open-file limit, head timeout, connection caps; final security
audit, M8), WebSocket upgrades are off, and the ``Server`` header is left out.
"""

import uvicorn

from app.core.config import get_settings
from app.core.server import connection_limit, protocol_class, raise_open_file_limit


def main() -> None:
    settings = get_settings()
    open_files = raise_open_file_limit()
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        workers=1,
        http=protocol_class(settings.trusted_proxies, connection_limit(open_files)),
        # NetScope has no WebSockets; an upgraded connection would leave the guard behind.
        ws="none",
        server_header=False,
        proxy_headers=True,
        forwarded_allow_ips=settings.trusted_proxies,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
