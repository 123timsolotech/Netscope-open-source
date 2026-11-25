"""Authentication: first-run setup, login, sessions and password reset (brief section 7).

Sessions:
- The cookie holds a random token; the database stores only its SHA-256 hash.
- Sliding expiry: a session expires after 30 days without use. Each use pushes the expiry
  back to 30 days, at most once a day per session (to limit database writes).
- Absolute limit: 90 days after login a session ends however often it is used (owner
  decision, M2 security audit).
"""

import logging
import secrets
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Result, delete, func, select, update
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm.attributes import set_committed_value

from app.core.config import Settings
from app.core.ratelimit import FailureRateLimiter, address_key
from app.core.security import (
    burn_password_check,
    hash_password,
    hash_token,
    new_session_token,
    password_check_slot,
    password_needs_rehash,
    password_problem,
    prepare_password_checks,
    tokens_match,
    username_problem,
    verify_password,
)
from app.core.timeutil import utcnow
from app.models import Session, User
from app.services.errors import InvalidInputError, Issue, ServiceError

logger = logging.getLogger("netscope.auth")

SESSION_LIFETIME = timedelta(days=30)
SESSION_RENEW_INTERVAL = timedelta(days=1)
# Owner decision (M2 security audit): log in again at least every 90 days, however often the
# session is used, so a stolen cookie stops working eventually.
SESSION_MAX_AGE = timedelta(days=90)
# Longest cookie value we bother hashing; real tokens are 43 characters.
MAX_TOKEN_LENGTH = 256
SETUP_TOKEN_BYTES = 18  # 24 characters
SETUP_TOKEN_MIN_LENGTH = 20  # for NETSCOPE_SETUP_TOKEN


class InvalidCredentialsError(ServiceError):
    def __init__(self) -> None:
        super().__init__("Invalid username or password.")


class InvalidSetupTokenError(ServiceError):
    def __init__(self) -> None:
        super().__init__("Invalid setup token.")


class SetupUnavailableError(ServiceError):
    def __init__(self) -> None:
        super().__init__("Setup is already complete.")


class NoAdminAccountError(ServiceError):
    def __init__(self) -> None:
        super().__init__(
            "No admin account exists yet. Finish setup in the browser, or set "
            "NETSCOPE_ADMIN_PASSWORD and start NetScope again (Docker: docker compose up -d)."
        )


class TooManyAttemptsError(ServiceError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Too many failed attempts. Try again in {retry_after} seconds.")
        self.retry_after = retry_after


class LoginBusyError(TooManyAttemptsError):
    """Too many login checks are already running or waiting (a flood of guesses)."""

    RETRY_AFTER = 2

    def __init__(self) -> None:
        super().__init__(self.RETRY_AFTER)
        self.message = "Too many login attempts at the moment. Try again in a few seconds."


@dataclass
class SetupState:
    """One-time setup token, kept in memory only. None once an admin exists."""

    token: str | None
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


@dataclass(frozen=True)
class NewSession:
    token: str  # goes into the cookie; never stored
    expires_at: datetime
    user: User


@dataclass(frozen=True)
class AuthenticatedSession:
    user: User
    session: Session
    renewed: bool  # expiry was pushed back; the cookie should be re-sent


# --- Accounts ------------------------------------------------------------------------------


def admin_exists(db: DbSession) -> bool:
    return db.scalar(select(func.count()).select_from(User)) != 0


def get_admin(db: DbSession) -> User | None:
    return db.scalars(select(User).order_by(User.created_at).limit(1)).first()


def find_user(db: DbSession, username: str) -> User | None:
    """Usernames are matched case-insensitively (they are ASCII only)."""
    return db.scalars(
        select(User).where(func.lower(User.username) == username.strip().lower())
    ).first()


def _check_new_credentials(username: str, password: str) -> None:
    issues = [
        Issue((field,), problem, f"invalid_{field}")
        for field, problem in (
            ("username", username_problem(username)),
            ("password", password_problem(password)),
        )
        if problem
    ]
    if issues:
        raise InvalidInputError(issues)


def create_admin(db: DbSession, username: str, password: str) -> User:
    """Create the single admin account. Fails if one already exists."""
    username = username.strip()
    _check_new_credentials(username, password)
    if admin_exists(db):
        raise SetupUnavailableError()
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    return user


def reset_password(db: DbSession, new_password: str) -> User:
    """Set a new admin password and log out every session (CLI ``reset-password``)."""
    problem = password_problem(new_password)
    if problem:
        raise InvalidInputError(Issue(("password",), problem, "invalid_password"))
    user = get_admin(db)
    if user is None:
        raise NoAdminAccountError()
    user.password_hash = hash_password(new_password)
    db.execute(delete(Session).where(Session.user_id == user.id))
    db.commit()
    return user


# --- First-run setup -------------------------------------------------------------------------


def _announce(message: str) -> None:
    """Print to stderr whatever the log level, so the setup token can never be hidden."""
    print(message, file=sys.stderr, flush=True)


def bootstrap(db: DbSession, settings: Settings) -> SetupState:
    """Run at startup: create the admin from the environment, or prepare a setup token."""
    prepare_password_checks()
    if admin_exists(db):
        if settings.admin_password is not None:
            logger.info("NETSCOPE_ADMIN_PASSWORD is ignored: an admin account already exists.")
        return SetupState(token=None)

    if settings.admin_password is not None:
        try:
            user = create_admin(
                db, settings.admin_username, settings.admin_password.get_secret_value()
            )
        except InvalidInputError as error:
            raise RuntimeError(
                f"Cannot create the admin account from NETSCOPE_ADMIN_USERNAME / "
                f"NETSCOPE_ADMIN_PASSWORD: {error.message}"
            ) from error
        logger.info("Created admin account '%s' from NETSCOPE_ADMIN_PASSWORD.", user.username)
        return SetupState(token=None)

    if settings.setup_token is not None:
        token = settings.setup_token.get_secret_value()
        if len(token) < SETUP_TOKEN_MIN_LENGTH:
            raise RuntimeError(
                f"NETSCOPE_SETUP_TOKEN must be at least {SETUP_TOKEN_MIN_LENGTH} characters long."
            )
        _announce("No admin account yet. Open NetScope and enter NETSCOPE_SETUP_TOKEN.")
    else:
        token = secrets.token_urlsafe(SETUP_TOKEN_BYTES)
        _announce(
            f"{'=' * 72}\nNo admin account yet. Open NetScope in your browser and enter this "
            f"one-time setup token:\n\n    {token}\n\nThe token changes every time NetScope "
            f"restarts until setup is complete.\n{'=' * 72}"
        )
    return SetupState(token=token)


def complete_setup(
    db: DbSession,
    state: SetupState,
    limiter: FailureRateLimiter,
    client_ip: str,
    setup_token: str,
    username: str,
    password: str,
) -> NewSession:
    """Create the admin with the one-time setup token and log them in."""
    # Answered before counting: once setup is done there is nothing to guess (and
    # GET /api/setup says so anyway). Checked again under the lock below.
    if state.token is None:
        raise SetupUnavailableError()
    key = ("setup", address_key(client_ip))
    retry_after = limiter.attempt(key)
    if retry_after is not None:
        raise TooManyAttemptsError(retry_after)

    # The lock makes "check, then create" atomic: two parallel requests cannot both
    # create an admin.
    with state.lock:
        if state.token is None or admin_exists(db):
            raise SetupUnavailableError()
        if not tokens_match(state.token, setup_token):
            raise InvalidSetupTokenError()
        user = create_admin(db, username, password)
        state.token = None

    limiter.reset(key)
    logger.info("Setup complete. Admin account '%s' created.", user.username)
    return start_session(db, user)


# --- Login and sessions ----------------------------------------------------------------------


def login(
    db: DbSession,
    limiter: FailureRateLimiter,
    client_ip: str,
    username: str,
    password: str,
) -> NewSession:
    key = ("login", address_key(client_ip))
    with password_check_slot() as admitted:
        # Refused before counting: a busy server must not use up the admin's attempts.
        if not admitted:
            raise LoginBusyError()
        # Counted before the slow password check, so parallel guesses cannot all slip through.
        retry_after = limiter.attempt(key)
        if retry_after is not None:
            raise TooManyAttemptsError(retry_after)

        user = find_user(db, username)
        if user is None:
            burn_password_check(password)
            raise InvalidCredentialsError()
        if not verify_password(user.password_hash, password):
            raise InvalidCredentialsError()

    limiter.reset(key)
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return start_session(db, user)


def start_session(db: DbSession, user: User, now: datetime | None = None) -> NewSession:
    now = now or utcnow()
    token = new_session_token()
    expires_at = now + SESSION_LIFETIME
    purge_expired_sessions(db, now)
    db.add(Session(id=hash_token(token), user_id=user.id, created_at=now, expires_at=expires_at))
    db.commit()
    return NewSession(token=token, expires_at=expires_at, user=user)


def authenticate(
    db: DbSession, token: str | None, now: datetime | None = None
) -> AuthenticatedSession | None:
    """The session for a cookie token, or None. Renews the expiry (sliding, but never past
    90 days after login)."""
    if not token or len(token) > MAX_TOKEN_LENGTH:
        return None
    now = now or utcnow()
    session = db.get(Session, hash_token(token))
    if session is None:
        return None
    hard_limit = session.created_at + SESSION_MAX_AGE
    if session.expires_at <= now or hard_limit <= now:
        _delete_session(db, session.id)
        return None

    renewed = False
    new_expiry = min(now + SESSION_LIFETIME, hard_limit)
    if new_expiry - session.expires_at >= SESSION_RENEW_INTERVAL:
        # A plain UPDATE (not an ORM flush): if another request deleted the session in the
        # meantime (logout in another tab, reset-password), this matches 0 rows instead of
        # raising.
        result = db.execute(
            update(Session)
            .where(Session.id == session.id)
            .values(expires_at=new_expiry)
            .execution_options(synchronize_session=False)
        )
        db.commit()
        if _rowcount(result) == 0:
            return None
        set_committed_value(session, "expires_at", new_expiry)
        renewed = True

    user = db.get(User, session.user_id)
    if user is None:  # cannot happen with foreign keys on; be safe anyway
        return None
    return AuthenticatedSession(user=user, session=session, renewed=renewed)


def session_is_live(db: DbSession, token: str | None, now: datetime | None = None) -> bool:
    """True if ``token`` belongs to an unexpired session. Read-only: no renewal."""
    if not token or len(token) > MAX_TOKEN_LENGTH:
        return False
    session = db.get(Session, hash_token(token))
    now = now or utcnow()
    return (
        session is not None
        and session.expires_at > now
        and session.created_at + SESSION_MAX_AGE > now
    )


def logout(db: DbSession, session: Session) -> None:
    _delete_session(db, session.id)


def change_password(
    db: DbSession,
    limiter: FailureRateLimiter,
    client_ip: str,
    current: AuthenticatedSession,
    current_password: str,
    new_password: str,
) -> NewSession:
    """Settings -> Account (M8). A wrong current password is counted like a failed login
    (5 per minute per address, then TooManyAttemptsError) and raises InvalidInputError on
    ``current_password``. On success: the new hash, every session of the admin deleted, and a
    new session for this browser (returned).

    A wrong password is a 422, not a 401: the frontend treats a 401 as "the session ended".
    The new password's rules are checked by the request schema (``NewPassword``).
    """
    key = ("password", address_key(client_ip))
    with password_check_slot() as admitted:
        # As at login: refused before counting, so a busy server uses up no attempts.
        if not admitted:
            raise LoginBusyError()
        # Counted before the slow check, so parallel guesses cannot all slip through.
        retry_after = limiter.attempt(key)
        if retry_after is not None:
            raise TooManyAttemptsError(retry_after)
        user = current.user
        if not verify_password(user.password_hash, current_password):
            raise InvalidInputError(
                Issue(
                    ("current_password",),
                    "The current password is not correct.",
                    "wrong_password",
                )
            )

    limiter.reset(key)
    others = count_other_sessions(db, current)
    user.password_hash = hash_password(new_password)
    # Every session ends, this one too (a stolen cookie must not survive the change);
    # start_session commits the hash, the deletion and the new session together.
    db.execute(delete(Session).where(Session.user_id == user.id))
    new = start_session(db, user)
    logger.info("Password changed; %d other sessions logged out.", others)
    return new


def count_other_sessions(db: DbSession, current: AuthenticatedSession) -> int:
    """Live sessions (not expired, under 90 days old) of the admin, except this one."""
    now = utcnow()
    return (
        db.scalar(
            select(func.count())
            .select_from(Session)
            .where(
                Session.user_id == current.user.id,
                Session.id != current.session.id,
                Session.expires_at > now,
                Session.created_at > now - SESSION_MAX_AGE,
            )
        )
        or 0
    )


def end_other_sessions(db: DbSession, current: AuthenticatedSession) -> int:
    """Delete every other session of the admin; returns how many."""
    result = db.execute(
        delete(Session).where(Session.user_id == current.user.id, Session.id != current.session.id)
    )
    db.commit()
    count = _rowcount(result)
    logger.info("Logged out %d other sessions.", count)
    return count


def _delete_session(db: DbSession, session_id: str) -> None:
    """Delete by id; does nothing if a parallel request already deleted it."""
    db.execute(delete(Session).where(Session.id == session_id))
    db.commit()


def _rowcount(result: Result[Any]) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


def purge_expired_sessions(db: DbSession, now: datetime | None = None) -> int:
    """Delete expired sessions. Returns how many were deleted (not committed here)."""
    result = db.execute(delete(Session).where(Session.expires_at <= (now or utcnow())))
    return _rowcount(result)
