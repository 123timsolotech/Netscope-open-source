"""Category CRUD (session required)."""

from uuid import UUID

from fastapi import APIRouter
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from app.api.deps import Db
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate
from app.services import categories as category_service
from app.services.categories import CategoryInfo

router = APIRouter(prefix="/categories", tags=["categories"])


def _out(info: CategoryInfo) -> CategoryOut:
    category = info.category
    return CategoryOut(
        id=category.id,
        name=category.name,
        color=category.color,
        icon=category.icon,
        device_count=info.device_count,
    )


@router.get("")
def list_categories(db: Db) -> list[CategoryOut]:
    return [_out(info) for info in category_service.list_categories(db)]


@router.post("", status_code=HTTP_201_CREATED)
def create_category(body: CategoryCreate, db: Db) -> CategoryOut:
    return _out(category_service.create_category(db, body))


@router.patch("/{category_id}")
def update_category(category_id: UUID, body: CategoryUpdate, db: Db) -> CategoryOut:
    return _out(category_service.update_category(db, str(category_id), body))


@router.delete("/{category_id}", status_code=HTTP_204_NO_CONTENT)
def delete_category(category_id: UUID, db: Db) -> None:
    """Devices in this category stay, without a category."""
    category_service.delete_category(db, str(category_id))
