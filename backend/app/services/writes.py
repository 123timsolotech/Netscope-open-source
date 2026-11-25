"""Committing writes so that races give the usual 422 or 404, never a 500.

Rules are checked before writing, but a parallel request can still win the race between the
check and the commit (take the same name, delete the category or the device itself).
"""

from collections.abc import Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm.exc import StaleDataError

from app.services.errors import NotFoundError


def commit(
    db: DbSession,
    *,
    not_found: str,
    recheck: Callable[[], None] | None = None,
    steps: Callable[[], None] | None = None,
) -> None:
    """Run ``steps`` (writes that need their own flush), then commit.

    - IntegrityError (a constraint failed): roll back and run ``recheck``, which raises the
      usual InvalidInputError or NotFoundError; if it finds nothing, the error is re-raised.
    - StaleDataError (the row being updated was deleted meanwhile): roll back, NotFoundError.
    """
    try:
        if steps is not None:
            steps()
        db.commit()
    except IntegrityError:
        db.rollback()
        if recheck is not None:
            recheck()
        raise
    except StaleDataError:
        db.rollback()
        raise NotFoundError(not_found) from None
