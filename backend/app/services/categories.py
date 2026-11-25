"""Categories: names unique regardless of case (brief section 6)."""

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as DbSession

from app.models import Category, Device
from app.models.base import name_key
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.errors import InvalidInputError, Issue, NotFoundError
from app.services.writes import commit

NOT_FOUND = "Category not found."


@dataclass(frozen=True)
class CategoryInfo:
    category: Category
    device_count: int


def list_categories(db: DbSession) -> list[CategoryInfo]:
    rows = db.execute(
        select(Category, func.count(Device.id))
        .outerjoin(Device, Device.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.name_key)
    )
    return [CategoryInfo(category, count) for category, count in rows]


def get_category(db: DbSession, category_id: str) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise NotFoundError(NOT_FOUND)
    return category


def create_category(db: DbSession, data: CategoryCreate) -> CategoryInfo:
    _check_name(db, data.name, category_id=None)
    category = Category(name=data.name, color=data.color, icon=data.icon)
    db.add(category)
    commit(db, not_found=NOT_FOUND, recheck=lambda: _check_name(db, data.name, category_id=None))
    return CategoryInfo(category, 0)


def update_category(db: DbSession, category_id: str, data: CategoryUpdate) -> CategoryInfo:
    """Partial update: fields left out stay unchanged."""
    category = get_category(db, category_id)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        _check_name(db, changes["name"], category_id=category.id)
    for field, value in changes.items():
        setattr(category, field, value)
    commit(
        db,
        not_found=NOT_FOUND,
        recheck=lambda: _check_name(db, changes.get("name", ""), category_id=category_id),
    )
    return CategoryInfo(category, _device_count(db, category.id))


def delete_category(db: DbSession, category_id: str) -> None:
    """Its devices stay, without a category (ON DELETE SET NULL)."""
    result = db.execute(delete(Category).where(Category.id == category_id))
    db.commit()
    if not getattr(result, "rowcount", 0):
        raise NotFoundError(NOT_FOUND)


def _check_name(db: DbSession, name: str, category_id: str | None) -> None:
    if not name:
        return
    existing = db.scalars(select(Category).where(Category.name_key == name_key(name))).first()
    if existing is not None and existing.id != category_id:
        raise InvalidInputError(
            Issue(
                ("name",), f'A category named "{existing.name}" already exists.', "duplicate_name"
            )
        )


def _device_count(db: DbSession, category_id: str) -> int:
    return db.scalar(select(func.count(Device.id)).where(Device.category_id == category_id)) or 0
