"""Serve the built frontend with SPA fallback (brief section 4).

- Unknown paths under /api return a JSON 404.
- A path that matches a file in the build folder returns that file.
- Any other path returns index.html, so the frontend's own routes work after a reload.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.status import HTTP_404_NOT_FOUND

API_PREFIX = "api"
# Vite puts content-hashed files in assets/, so they can be cached forever.
IMMUTABLE_DIR = "assets"


def _resolve_file(dist: Path, request_path: str) -> Path | None:
    """The file inside ``dist`` for ``request_path``, or None. Never escapes ``dist``."""
    if not request_path or "\x00" in request_path:
        return None
    try:
        candidate = (dist / request_path).resolve()
        if not candidate.is_relative_to(dist) or not candidate.is_file():
            return None
    except (OSError, ValueError):  # names the file system rejects (too long, ...)
        return None
    return candidate


def register_spa(app: FastAPI, dist: Path) -> None:
    dist = dist.resolve()
    index_file = dist / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path == API_PREFIX or full_path.startswith(f"{API_PREFIX}/"):
            raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Not Found")

        if not index_file.is_file():
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail="Frontend not built. Run `npm run build` in frontend/.",
            )

        file = _resolve_file(dist, full_path)
        if file is not None:
            cache = (
                "public, max-age=31536000, immutable"
                if full_path.startswith(f"{IMMUTABLE_DIR}/")
                else "no-cache"
            )
            return FileResponse(file, headers={"Cache-Control": cache})

        return FileResponse(index_file, headers={"Cache-Control": "no-cache"})
