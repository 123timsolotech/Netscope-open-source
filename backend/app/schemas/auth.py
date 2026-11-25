"""Request and response shapes for setup and login."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, StringConstraints

from app.core.security import (
    PASSWORD_MAX_LENGTH,
    USERNAME_MAX_LENGTH,
    password_problem,
    username_problem,
)
from app.schemas.common import RequestModel, SafeStr


def _valid_username(value: str) -> str:
    problem = username_problem(value)
    if problem:
        raise ValueError(problem)
    return value


def _valid_new_password(value: str) -> str:
    problem = password_problem(value)
    if problem:
        raise ValueError(problem)
    return value


NewUsername = Annotated[
    SafeStr, StringConstraints(strip_whitespace=True), AfterValidator(_valid_username)
]
NewPassword = Annotated[SafeStr, AfterValidator(_valid_new_password)]


class SetupStatus(BaseModel):
    setup_required: bool


class SetupRequest(RequestModel):
    setup_token: Annotated[SafeStr, StringConstraints(min_length=1, max_length=256)]
    username: NewUsername
    password: NewPassword


class LoginRequest(RequestModel):
    # Only length limits here: login must not leak the account rules.
    username: Annotated[
        SafeStr,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=USERNAME_MAX_LENGTH),
    ]
    password: Annotated[SafeStr, StringConstraints(min_length=1, max_length=PASSWORD_MAX_LENGTH)]


class CurrentUser(BaseModel):
    username: str


class PasswordChange(RequestModel):
    """Settings -> Account (M8). A wrong current password is a 422 on ``current_password``
    (not a 401: the session is fine), counted like a failed login."""

    current_password: Annotated[
        SafeStr, StringConstraints(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    ]
    new_password: NewPassword


class SessionsOut(BaseModel):
    """Live sessions of the admin other than the one asking (M8, Settings -> Account)."""

    other_sessions: int
