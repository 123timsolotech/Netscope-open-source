"""Shared Pydantic types."""

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    PlainSerializer,
)
from pydantic_core import CoreSchema, PydanticCustomError, core_schema

from app.core.timeutil import to_iso_z
from app.services.errors import Issue

# Datetime that the API returns as ISO 8601 UTC with a trailing "Z" (brief section 6).
UtcDateTime = Annotated[datetime, PlainSerializer(to_iso_z, return_type=str, when_used="json")]

INVALID_TEXT_MESSAGE = "Text contains invalid characters."


def _utf8_safe(value: str) -> str:
    """Reject lone UTF-16 surrogates (JSON allows "\\ud800"): they cannot be stored or hashed."""
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError(INVALID_TEXT_MESSAGE) from None
    return value


# Every text field in a request body uses SafeStr or Text (which includes the same check).
SafeStr = Annotated[str, AfterValidator(_utf8_safe)]


def blank_to_none(value: Any) -> Any:
    """Forms send "" for empty optional inputs: blank text means "not set"."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


# Line breaks and other control characters. Other format characters (Cf) stay allowed: emoji
# sequences need the zero-width joiner.
_SINGLE_LINE_FORBIDDEN = frozenset({"Cc", "Zl", "Zp"})

# Invisible characters removed from single-line text, the way strip() removes spaces: they
# arrive by copy-paste (Windows pastes U+200E, web pages U+200B) and would make look-alike
# names ("nas" and "nas" + U+200B). Unicode's Default_Ignorable_Code_Point set plus U+2800
# (blank braille pattern) and the interlinear annotation marks, minus what emoji and some
# scripts need: ZWNJ/ZWJ (U+200C/D), variation selectors (U+FE00-FE0F, U+E0100-E01EF), emoji
# tag characters (U+E0020-E007F) and Mongolian variation selectors (U+180B-180D, U+180F).
_INVISIBLE_RANGES = (
    (0x00AD, 0x00AD),  # soft hyphen
    (0x034F, 0x034F),  # combining grapheme joiner
    (0x061C, 0x061C),  # Arabic letter mark
    (0x115F, 0x1160),  # Hangul fillers
    (0x17B4, 0x17B5),  # invisible Khmer vowels
    (0x180E, 0x180E),  # Mongolian vowel separator
    (0x200B, 0x200B),  # zero-width space
    (0x200E, 0x200F),  # left-to-right / right-to-left marks
    (0x202A, 0x202E),  # bidi embeddings and overrides
    (0x2060, 0x206F),  # word joiner, invisible operators, bidi isolates, deprecated formats
    (0x2800, 0x2800),  # braille pattern blank
    (0x3164, 0x3164),  # Hangul filler
    (0xFEFF, 0xFEFF),  # byte order mark / zero-width no-break space
    (0xFFA0, 0xFFA0),  # half-width Hangul filler
    (0xFFF0, 0xFFFB),  # unassigned specials, interlinear annotation
    (0x1BCA0, 0x1BCA3),  # shorthand format controls
    (0x1D173, 0x1D17A),  # musical symbol format controls
    (0xE0000, 0xE001F),  # language tag and unassigned
    (0xE0080, 0xE00FF),
    (0xE01F0, 0xE0FFF),
)
_INVISIBLE = frozenset(
    chr(code) for first, last in _INVISIBLE_RANGES for code in range(first, last + 1)
)
_SPACE_RUNS = re.compile(" {2,}")
# A name needs at least one character outside these (a lone accent or a joiner is not a name).
_NOT_VISIBLE = frozenset({"Mn", "Me", "Cf", "Zs"})


def clean_single_line(value: str) -> str:
    """NFC; invisible characters removed; every space character (no-break, ideographic, ...)
    turned into a plain space and runs of spaces collapsed. "nas\u00a0box" and "nas  box"
    become "nas box", so they cannot pass as different names."""
    value = unicodedata.normalize("NFC", value)
    value = "".join(
        " " if unicodedata.category(ch) == "Zs" else ch for ch in value if ch not in _INVISIBLE
    )
    # Removing a character can leave a sequence that composes differently: normalize again.
    return unicodedata.normalize("NFC", _SPACE_RUNS.sub(" ", value))


@dataclass(frozen=True)
class Text:
    """Request text: ``Annotated[str, Text(100)]`` or ``Annotated[str | None, Text(100,
    optional=True)]``.

    In this order: normalizes (NFC; multi-line text turns CRLF into LF; single-line text is
    cleaned by :func:`clean_single_line`), strips outer whitespace, checks the length (at least
    1 character after stripping), rejects lone surrogates (like SafeStr) and control characters
    (single-line fields also reject line breaks and tabs, and need one visible character).
    ``optional`` turns blank input into None. Put ``Text`` first in ``Annotated``: it builds
    the whole string schema itself, so annotations before it are ignored.

    (Pydantic applies ``StringConstraints`` placed after a validator only after the fact:
    ``"   "`` would pass ``min_length=1`` and strip after the length check, hence this class.)
    """

    max_length: int
    multiline: bool = False
    optional: bool = False

    def __get_pydantic_core_schema__(
        self, _source: Any, _handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        schema: CoreSchema = core_schema.no_info_before_validator_function(
            self._normalize,
            core_schema.no_info_after_validator_function(
                self._check,
                core_schema.str_schema(
                    strip_whitespace=True, min_length=1, max_length=self.max_length
                ),
            ),
        )
        if self.optional:
            schema = core_schema.no_info_before_validator_function(
                self._blank_to_none, core_schema.nullable_schema(schema)
            )
        return schema

    def _blank_to_none(self, value: Any) -> Any:
        """Blank after cleaning (only spaces and invisible characters) means "not set"."""
        return blank_to_none(self._normalize(value))

    def _normalize(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value  # the string schema reports the wrong type
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return value  # the string schema rejects lone surrogates
        if self.multiline:
            return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
        return clean_single_line(value)

    def _check(self, value: str) -> str:
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise PydanticCustomError("invalid_characters", INVALID_TEXT_MESSAGE) from None
        if self.multiline:
            if any(unicodedata.category(ch) == "Cc" and ch not in "\n\t" for ch in value):
                raise PydanticCustomError(
                    "control_characters", "Remove control characters from the text."
                )
        elif any(unicodedata.category(ch) in _SINGLE_LINE_FORBIDDEN for ch in value):
            raise PydanticCustomError(
                "single_line", "Use a single line without tabs or control characters."
            )
        elif all(unicodedata.category(ch) in _NOT_VISIBLE for ch in value):
            raise PydanticCustomError(
                "no_visible_characters", "Enter at least one visible character."
            )
        return value


def omittable() -> Any:
    """Default for a PATCH field that may be left out but must not be null.

    The default (None) is never validated, so leaving the field out works, while an explicit
    null fails the field's type. Services read only the fields that were sent
    (``model_dump(exclude_unset=True)`` / ``model_fields_set``), never the None default.
    """
    return Field(default=None)


class RequestModel(BaseModel):
    """Base for request bodies: unknown fields are an error (decision M2.11)."""

    model_config = ConfigDict(extra="forbid")


class IssueOut(BaseModel):
    """A validation error or warning, in FastAPI's error item shape (decision M3)."""

    type: str
    loc: list[str | int]
    msg: str

    @classmethod
    def of(cls, issue: Issue) -> "IssueOut":
        return cls(type=issue.type, loc=["body", *issue.loc], msg=issue.msg)
