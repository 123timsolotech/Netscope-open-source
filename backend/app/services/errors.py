"""Errors raised by the services layer. The API layer maps them to HTTP responses."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Issue:
    """One problem (or warning) about the input, tied to a field.

    ``loc`` is the path inside the request body, for example ``("services", 1, "port")``.
    The API adds ``"body"`` in front, so business-rule errors look exactly like FastAPI's
    own validation errors (``{"type", "loc", "msg"}``, decision M3).
    """

    loc: tuple[str | int, ...]
    msg: str
    type: str


class ServiceError(Exception):
    """Base class. ``message`` is safe to show to the user."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidInputError(ServiceError):
    """Input breaks one or more business rules. The API answers 422 listing every issue."""

    def __init__(self, issues: Issue | Sequence[Issue]) -> None:
        self.issues: tuple[Issue, ...] = (issues,) if isinstance(issues, Issue) else tuple(issues)
        if not self.issues:
            raise ValueError("InvalidInputError needs at least one issue.")
        super().__init__(" ".join(issue.msg for issue in self.issues))


class NotFoundError(ServiceError):
    """The resource named in the URL does not exist (404)."""
