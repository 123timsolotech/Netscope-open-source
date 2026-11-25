"""Link CRUD (session required). Links are undirected."""

from uuid import UUID

from fastapi import APIRouter
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from app.api.deps import Db
from app.schemas.link import LinkCreate, LinkOut, LinkUpdate
from app.services import links as link_service

router = APIRouter(prefix="/links", tags=["links"])


@router.get("")
def list_links(db: Db) -> list[LinkOut]:
    return [LinkOut.model_validate(link) for link in link_service.list_links(db)]


@router.post("", status_code=HTTP_201_CREATED)
def create_link(body: LinkCreate, db: Db) -> LinkOut:
    return LinkOut.model_validate(link_service.create_link(db, body))


@router.patch("/{link_id}")
def update_link(link_id: UUID, body: LinkUpdate, db: Db) -> LinkOut:
    return LinkOut.model_validate(link_service.update_link(db, str(link_id), body))


@router.delete("/{link_id}", status_code=HTTP_204_NO_CONTENT)
def delete_link(link_id: UUID, db: Db) -> None:
    link_service.delete_link(db, str(link_id))
