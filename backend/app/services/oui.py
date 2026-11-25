"""Offline MAC vendor lookup from the IEEE registries (brief sections 2 and 4).

``app/data/oui.csv`` holds ``prefix,vendor`` rows built by ``scripts/update_oui.py`` from the
three IEEE lists: MA-L (24-bit prefixes, 6 hex digits), MA-M (28-bit, 7) and MA-S (36-bit, 9).
The most specific prefix wins: a block that the IEEE split into smaller ones is listed in
MA-L as "IEEE Registration Authority", and the real owner is in MA-M or MA-S.

The file is read once at startup and kept in memory. Nothing here touches the network.
"""

import csv
import functools
import io
import logging
import os
import re
import tempfile
import unicodedata
from collections.abc import Iterable, Mapping
from pathlib import Path

logger = logging.getLogger("netscope.oui")

OUI_FILE = Path(__file__).resolve().parents[1] / "data" / "oui.csv"
FILE_HEADER = ["prefix", "vendor"]
PREFIX_LENGTHS = (9, 7, 6)  # most specific first: MA-S, MA-M, MA-L
VENDOR_MAX_LENGTH = 255  # devices.vendor column
_PREFIX = re.compile(r"[0-9A-F]+")


class OuiDatabase:
    """MAC prefix (upper-case hex, 6, 7 or 9 digits) -> vendor name."""

    def __init__(self, vendors: Mapping[str, str] | None = None) -> None:
        self._vendors = dict(vendors or {})
        for prefix in self._vendors:
            _check_prefix(prefix)

    def __len__(self) -> int:
        return len(self._vendors)

    def lookup(self, mac: str) -> str | None:
        """Vendor for a normalized MAC (``AA:BB:CC:DD:EE:FF``), or None if unknown."""
        digits = mac.replace(":", "").upper()
        for length in PREFIX_LENGTHS:
            vendor = self._vendors.get(digits[:length])
            if vendor is not None:
                return vendor
        return None


def _check_prefix(prefix: str) -> None:
    if len(prefix) not in PREFIX_LENGTHS or not _PREFIX.fullmatch(prefix):
        raise ValueError(
            f"Invalid MAC prefix {prefix!r}: expected 6, 7 or 9 upper-case hex digits."
        )


def read_oui_file(path: Path) -> OuiDatabase:
    """Read a ``prefix,vendor`` file written by :func:`write_oui_file`."""
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        header = next(reader, None)
        if header != FILE_HEADER:
            raise ValueError(f"{path}: expected the header {','.join(FILE_HEADER)!r}.")
        vendors: dict[str, str] = {}
        for line_number, row in enumerate(reader, start=2):
            if len(row) != len(FILE_HEADER):
                raise ValueError(f"{path}, line {line_number}: expected 2 columns.")
            prefix, vendor = row
            try:
                _check_prefix(prefix)
            except ValueError as error:
                raise ValueError(f"{path}, line {line_number}: {error}") from None
            vendors[prefix] = vendor
    return OuiDatabase(vendors)


@functools.cache
def load_bundled_oui(path: Path = OUI_FILE) -> OuiDatabase:
    """The bundled list, read once per process. Missing file: lookups return None."""
    if not path.is_file():
        logger.warning("MAC vendor list %s not found; vendors will not be looked up.", path)
        return OuiDatabase()
    database = read_oui_file(path)
    logger.info("Loaded %d MAC vendor prefixes.", len(database))
    return database


# --- Building the file from the IEEE lists (used by scripts/update_oui.py) -----------------


def clean_vendor_name(name: str) -> str:
    """Single spaces, no control or invisible format characters (IEEE data has tabs, zero-width
    spaces and non-breaking spaces), at most ``VENDOR_MAX_LENGTH`` characters."""
    visible = "".join(
        " " if ch.isspace() else ch
        for ch in name
        if ch.isspace() or unicodedata.category(ch) not in {"Cc", "Cf"}
    )
    return " ".join(visible.split())[:VENDOR_MAX_LENGTH]


def parse_ieee_csv(text: str, prefix_length: int) -> dict[str, str]:
    """Prefix -> vendor from one IEEE registry CSV
    (``Registry,Assignment,Organization Name,Organization Address``).

    Raises ValueError if the format is not what we expect, so a changed or broken download
    never replaces a good file. A few old prefixes are listed more than once; their distinct
    names are joined with " / ".
    """
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or not {"Assignment", "Organization Name"} <= set(
        reader.fieldnames
    ):
        raise ValueError("Not an IEEE registry CSV: Assignment / Organization Name missing.")
    names: dict[str, set[str]] = {}
    for line_number, row in enumerate(reader, start=2):
        prefix = (row.get("Assignment") or "").strip().upper()
        if len(prefix) != prefix_length or not _PREFIX.fullmatch(prefix):
            raise ValueError(
                f"Line {line_number}: assignment {prefix!r} is not {prefix_length} hex digits."
            )
        name = clean_vendor_name(row.get("Organization Name") or "")
        if name:
            names.setdefault(prefix, set()).add(name)
    return {
        prefix: " / ".join(sorted(found))[:VENDOR_MAX_LENGTH] for prefix, found in names.items()
    }


def write_oui_file(vendors: Mapping[str, str], path: Path) -> None:
    """Write ``prefix,vendor`` rows sorted by prefix (stable diffs), replacing ``path``
    atomically."""
    rows: Iterable[tuple[str, str]] = sorted(vendors.items())
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file, lineterminator="\n")
            writer.writerow(FILE_HEADER)
            for prefix, vendor in rows:
                _check_prefix(prefix)
                writer.writerow([prefix, vendor])
        os.chmod(temp_name, 0o644)  # mkstemp creates 0600; the app may run as another user
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
