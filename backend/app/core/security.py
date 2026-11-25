"""Password hashing, session tokens and credential rules (brief section 7)."""

import hashlib
import re
import secrets
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# Credential rules (owner decision, M2).
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 64
# Matched with fullmatch (unlike "$", it does not accept a trailing newline).
USERNAME_PATTERN = r"[A-Za-z0-9._-]+"
PASSWORD_MIN_LENGTH = 20
# Upper bound so nobody can make the server hash megabytes of input.
PASSWORD_MAX_LENGTH = 1024

SESSION_TOKEN_BYTES = 32

_username_re = re.compile(USERNAME_PATTERN)
_password_hasher = PasswordHasher()  # argon2id, library defaults (RFC 9106 low-memory profile)

# Each argon2 hash uses 64 MiB of memory (about 60 ms). Cap how many run at once, so a burst
# of logins cannot use gigabytes of memory or block every worker thread.
ARGON2_MAX_CONCURRENT = 2
_argon2_slots = threading.BoundedSemaphore(ARGON2_MAX_CONCURRENT)

# Login checks that may run or wait at the same time. Each waiting one holds one of the
# server's worker threads, so without this cap a flood of login guesses (from many addresses)
# stalled every other request, even for the logged-in admin (security audit, M2).
PASSWORD_CHECKS_MAX_PENDING = 8
_pending_checks = threading.BoundedSemaphore(PASSWORD_CHECKS_MAX_PENDING)


@contextmanager
def password_check_slot() -> Iterator[bool]:
    """Yields True if a login check may go ahead now, False if too many are pending.

    Never waits: a refused check should be answered at once (429), not queued.
    """
    admitted = _pending_checks.acquire(blocking=False)
    try:
        yield admitted
    finally:
        if admitted:
            _pending_checks.release()


def hash_password(password: str) -> str:
    with _argon2_slots:
        return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    with _argon2_slots:
        try:
            return _password_hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False


def password_needs_rehash(password_hash: str) -> bool:
    """True when the hash was made with older parameters than the current defaults."""
    return _password_hasher.check_needs_rehash(password_hash)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return hash_password(secrets.token_urlsafe(32))


def prepare_password_checks() -> None:
    """Create the dummy hash at startup. Made lazily, the first login with an unknown username
    took two hashes (about twice as long), which told that the username was wrong."""
    _dummy_hash()


def burn_password_check(password: str) -> None:
    """Spend the same time as a real check, for unknown usernames.

    Without this, a login for a username that does not exist would answer faster than
    one for the real admin, which tells an attacker the admin's username.
    """
    verify_password(_dummy_hash(), password)


def new_session_token() -> str:
    """Random token for the session cookie (256 bits)."""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 (hex) of a session token. Only this is stored (brief sections 6 and 7).

    No salt or slow hash is needed: the tokens are 256-bit random values, not passwords.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(expected: str, given: str) -> bool:
    """Constant-time comparison, so response time does not leak how much matched."""
    return secrets.compare_digest(expected.encode("utf-8"), given.encode("utf-8"))


def username_problem(username: str) -> str | None:
    """Why ``username`` is not allowed, or None if it is fine."""
    if not USERNAME_MIN_LENGTH <= len(username) <= USERNAME_MAX_LENGTH:
        return f"Username must be {USERNAME_MIN_LENGTH} to {USERNAME_MAX_LENGTH} characters long."
    if not _username_re.fullmatch(username):
        return "Username may only contain letters, digits, dots, underscores and hyphens."
    return None


def password_problem(password: str) -> str | None:
    """Why ``password`` is not allowed as a new password, or None if it is fine."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."
    if len(password) > PASSWORD_MAX_LENGTH:
        return f"Password must be at most {PASSWORD_MAX_LENGTH} characters long."
    return None
