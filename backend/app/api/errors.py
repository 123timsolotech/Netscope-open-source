"""Map service errors to HTTP responses, so routes stay thin."""

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette import status

from app.schemas.common import IssueOut
from app.services.auth import (
    InvalidCredentialsError,
    InvalidSetupTokenError,
    NoAdminAccountError,
    SetupUnavailableError,
    TooManyAttemptsError,
)
from app.services.backup import ImportBusyError, ImportConflictError
from app.services.errors import InvalidInputError, NotFoundError, ServiceError

STATUS_BY_ERROR: dict[type[ServiceError], int] = {
    InvalidCredentialsError: status.HTTP_401_UNAUTHORIZED,
    InvalidSetupTokenError: status.HTTP_403_FORBIDDEN,
    SetupUnavailableError: status.HTTP_409_CONFLICT,
    NoAdminAccountError: status.HTTP_409_CONFLICT,
    ImportConflictError: status.HTTP_409_CONFLICT,
    ImportBusyError: status.HTTP_409_CONFLICT,
    TooManyAttemptsError: status.HTTP_429_TOO_MANY_REQUESTS,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    InvalidInputError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


logger = logging.getLogger("netscope.api")

# SQLite's answer when another connection held the write lock for the whole busy timeout
# (5 s): a long import, or a slow disk. The request can simply be sent again.
DATABASE_LOCKED = "database is locked"
DATABASE_BUSY = "NetScope is busy. Try again in a few seconds."
DATABASE_BUSY_RETRY_AFTER = 5


async def _service_error_handler(_request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, ServiceError):  # registered for ServiceError only
        raise error
    if isinstance(error, InvalidInputError):
        # Same list format as request validation errors, so forms can show each issue
        # next to its field (decision M3).
        issues = [IssueOut.of(issue).model_dump() for issue in error.issues]
        return JSONResponse({"detail": issues}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
    status_code = next(
        (code for cls, code in STATUS_BY_ERROR.items() if isinstance(error, cls)),
        status.HTTP_400_BAD_REQUEST,
    )
    headers = None
    if isinstance(error, TooManyAttemptsError):
        headers = {"Retry-After": str(error.retry_after)}
    return JSONResponse({"detail": error.message}, status_code=status_code, headers=headers)


async def _validation_error_handler(_request: Request, error: Exception) -> JSONResponse:
    """FastAPI's 422 format, minus the ``input`` echo (it would send passwords back)."""
    if not isinstance(error, RequestValidationError):
        raise error
    errors = [{k: v for k, v in item.items() if k != "input"} for item in error.errors()]
    return JSONResponse(
        {"detail": jsonable_encoder(errors)}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
    )


async def _database_error_handler(request: Request, error: Exception) -> JSONResponse:
    """A busy database is a 503 with Retry-After (found in the M8 review: a 500 before); any
    other database error stays a 500 (re-raised to the server's own handler)."""
    if not isinstance(error, OperationalError):  # registered for OperationalError only
        raise error
    if DATABASE_LOCKED not in str(error.orig if error.orig is not None else error):
        raise error
    logger.warning(
        "The database stayed locked for the whole busy timeout; answered 503 to %s %s.",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        {"detail": DATABASE_BUSY},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        headers={"Retry-After": str(DATABASE_BUSY_RETRY_AFTER)},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ServiceError, _service_error_handler)
    app.add_exception_handler(OperationalError, _database_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
