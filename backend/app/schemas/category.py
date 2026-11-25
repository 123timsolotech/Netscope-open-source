"""Request and response shapes for categories."""

import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel
from pydantic_core import PydanticCustomError

from app.schemas.common import RequestModel, Text, omittable

CATEGORY_NAME_MAX_LENGTH = 64
ICON_MAX_LENGTH = 64
_COLOR = re.compile(r"#[0-9A-Fa-f]{6}")
# Lucide icon names are lower-case words joined by hyphens ("hard-drive"). The backend does
# not hold Lucide's list; the frontend shows a fallback icon for unknown names.
_ICON = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _color(value: str) -> str:
    if not _COLOR.fullmatch(value):
        raise PydanticCustomError("color", "Use a hex color like #60a5fa.")
    return value.lower()


def _icon(value: str) -> str:
    if not _ICON.fullmatch(value):
        raise PydanticCustomError("icon_name", "Use a Lucide icon name like hard-drive.")
    return value


CategoryName = Annotated[str, Text(CATEGORY_NAME_MAX_LENGTH)]
Color = Annotated[str, Text(7), AfterValidator(_color)]
IconName = Annotated[str, Text(ICON_MAX_LENGTH), AfterValidator(_icon)]


class CategoryCreate(RequestModel):
    name: CategoryName
    color: Color
    icon: IconName


class CategoryUpdate(RequestModel):
    """Partial update: fields left out stay unchanged. None of them can be null."""

    name: CategoryName = omittable()
    color: Color = omittable()
    icon: IconName = omittable()


class CategoryOut(BaseModel):
    id: str
    name: str
    color: str
    icon: str
    device_count: int
