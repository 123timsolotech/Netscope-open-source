"""About NetScope (M8, session required): the version shown on the Settings page."""

from fastapi import APIRouter

from app import __version__
from app.schemas.system import AboutOut

router = APIRouter(tags=["system"])


@router.get("/about")
def about() -> AboutOut:
    return AboutOut(version=__version__)
