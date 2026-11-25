"""Links between devices (brief section 6).

Links are undirected: they are stored with ``device_a_id < device_b_id``, so A-B and B-A are
the same row. No self-links, no duplicates. The database enforces both too (CHECK and UNIQUE,
decision M1.7); this module reports them as field issues first.
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from app.models import Device, Link
from app.schemas.link import LinkCreate, LinkUpdate
from app.services.errors import InvalidInputError, Issue, NotFoundError
from app.services.writes import commit

NOT_FOUND = "Link not found."


def list_links(db: DbSession) -> list[Link]:
    return list(db.scalars(select(Link).order_by(Link.device_a_id, Link.device_b_id)))


def get_link(db: DbSession, link_id: str) -> Link:
    link = db.get(Link, link_id)
    if link is None:
        raise NotFoundError(NOT_FOUND)
    return link


def create_link(db: DbSession, data: LinkCreate) -> Link:
    device_a_id, device_b_id = sorted((str(data.device_a_id), str(data.device_b_id)))
    _check_new_link(db, data)
    link = Link(
        device_a_id=device_a_id, device_b_id=device_b_id, link_type=data.link_type, label=data.label
    )
    db.add(link)
    # A parallel request may have created the same link or deleted a device meanwhile.
    commit(db, not_found=NOT_FOUND, recheck=lambda: _check_new_link(db, data))
    return link


def update_link(db: DbSession, link_id: str, data: LinkUpdate) -> Link:
    """Change the type or label. The devices cannot change: delete and create instead."""
    link = get_link(db, link_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(link, field, value)
    commit(db, not_found=NOT_FOUND)
    return link


def delete_link(db: DbSession, link_id: str) -> None:
    result = db.execute(delete(Link).where(Link.id == link_id))
    db.commit()
    if not getattr(result, "rowcount", 0):
        raise NotFoundError(NOT_FOUND)


def _check_new_link(db: DbSession, data: LinkCreate) -> None:
    issues: list[Issue] = []
    ids = {"device_a_id": str(data.device_a_id), "device_b_id": str(data.device_b_id)}
    for field, device_id in ids.items():
        if db.scalar(select(Device.id).where(Device.id == device_id)) is None:
            issues.append(Issue((field,), "Device not found.", "device_not_found"))
    if ids["device_a_id"] == ids["device_b_id"]:
        issues.append(Issue(("device_b_id",), "A device cannot be linked to itself.", "self_link"))
    elif not issues:
        low, high = sorted(ids.values())
        if db.scalar(select(Link.id).where(Link.device_a_id == low, Link.device_b_id == high)):
            issues.append(
                Issue(("device_b_id",), "These two devices are already linked.", "duplicate_link")
            )
    if issues:
        raise InvalidInputError(issues)
