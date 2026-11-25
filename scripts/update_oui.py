"""Refresh backend/app/data/oui.csv (offline MAC vendor list) from the IEEE registries.

Run from backend/:

    uv run python ../scripts/update_oui.py

Downloads the MA-L, MA-M and MA-S lists from standards-oui.ieee.org, keeps only
``prefix,vendor`` and writes the file sorted by prefix. Review the diff and commit it.
This is the only part of NetScope that contacts the internet, and only when you run it.
"""

import argparse
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.services.oui import OUI_FILE, parse_ieee_csv, write_oui_file

USER_AGENT = "netscope-oui-update"
TIMEOUT_SECONDS = 120
# The real lists total about 5 MB; anything far bigger is not what we asked for.
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class Registry:
    name: str
    url: str
    prefix_length: int
    # A smaller list means a broken or truncated download: keep the old file instead.
    min_entries: int


REGISTRIES = (
    Registry("MA-L", "https://standards-oui.ieee.org/oui/oui.csv", 6, 30_000),
    Registry("MA-M", "https://standards-oui.ieee.org/oui28/mam.csv", 7, 4_000),
    Registry("MA-S", "https://standards-oui.ieee.org/oui36/oui36.csv", 9, 4_000),
)


def download(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
        final_url: str = response.geturl()
        if not final_url.startswith("https://"):  # urllib follows redirects, also to http
            raise ValueError(f"{url} redirected to {final_url}, which is not HTTPS.")
        body: bytes = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(body) > MAX_DOWNLOAD_BYTES:
        raise ValueError(f"{url} is larger than {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB.")
    return body.decode("utf-8")


def update(output: Path, fetch: Callable[[str], str] = download) -> dict[str, int]:
    """Download all registries, then write ``output``. Returns the entry count per registry.

    Nothing is written unless every list downloaded and parsed.
    """
    vendors: dict[str, str] = {}
    counts: dict[str, int] = {}
    for registry in REGISTRIES:
        entries = parse_ieee_csv(fetch(registry.url), registry.prefix_length)
        if len(entries) < registry.min_entries:
            raise ValueError(
                f"{registry.name}: only {len(entries)} entries (expected at least "
                f"{registry.min_entries}). The download looks incomplete."
            )
        counts[registry.name] = len(entries)
        vendors.update(entries)  # prefix lengths differ, so registries never collide
    write_oui_file(vendors, output)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh the offline MAC vendor list.")
    parser.add_argument(
        "--output", type=Path, default=OUI_FILE, help=f"file to write (default: {OUI_FILE})"
    )
    args = parser.parse_args(argv)
    try:
        counts = update(args.output)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    summary = ", ".join(f"{name} {count}" for name, count in counts.items())
    print(f"Wrote {sum(counts.values())} prefixes ({summary}) to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
