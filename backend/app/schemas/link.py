"""Request and response shapes for links between devices."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import LinkType
from app.schemas.common import RequestModel, Text, omittable

LINK_LABEL_MAX_LENGTH = 100

LinkLabel = Annotated[str | None, Text(LINK_LABEL_MAX_LENGTH, optional=True)]


class LinkCreate(RequestModel):
    """Links are undirected: A-B and B-A are the same link."""

    device_a_id: UUID
    device_b_id: UUID
    link_type: LinkType = LinkType.ETHERNET
    label: LinkLabel = None


class LinkUpdate(RequestModel):
    """Partial update. The two devices cannot change: delete the link and create a new one."""

    link_type: LinkType = omittable()  # can be left out, not null
    label: LinkLabel = None


class LinkOut(BaseModel):
    """``device_a_id`` is always the smaller id (brief section 6)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    device_a_id: str
    device_b_id: str
    link_type: LinkType
    label: str | None
