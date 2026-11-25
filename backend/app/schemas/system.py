"""About NetScope (M8: the version on the Settings page, never in the public health check)."""

from pydantic import BaseModel


class AboutOut(BaseModel):
    version: str
