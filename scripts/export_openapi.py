"""Write the backend's OpenAPI schema to frontend/src/api/generated/openapi.json.

Run from backend/ after changing a route or schema, then regenerate the frontend types:

    uv run python ../scripts/export_openapi.py
    cd ../frontend && npm run gen:api

Commit both files. ``backend/tests/test_openapi_snapshot.py`` fails while the file is stale,
and CI checks that the frontend types match it. No server is started and nothing is fetched.
"""

import json
import sys
from pathlib import Path

from app.main import create_app

OPENAPI_FILE = Path(__file__).resolve().parents[1] / "frontend/src/api/generated/openapi.json"


def render() -> str:
    """The schema as committed: two-space indents, keys in FastAPI's order, final newline."""
    return json.dumps(create_app().openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    OPENAPI_FILE.parent.mkdir(parents=True, exist_ok=True)
    OPENAPI_FILE.write_text(render(), encoding="utf-8", newline="\n")
    print(f"Wrote {OPENAPI_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
