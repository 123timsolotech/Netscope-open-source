"""Request and response shapes for the user's settings (M6: status checks).

The ranges live here; ``app/services/app_settings.py`` uses the same ones to check stored
values, and adds the rule that ties the timeout to the interval.
"""

from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, Field, Strict

from app.schemas.common import RequestModel, omittable


@dataclass(frozen=True)
class Limits:
    low: int
    high: int
    default: int


# Owner decision, M6.
CHECK_INTERVAL_SECONDS = Limits(10, 3600, 30)
CHECK_TIMEOUT_SECONDS = Limits(1, 30, 5)
FAILURES_BEFORE_DOWN = Limits(1, 10, 2)
RETENTION_DAYS = Limits(1, 30, 7)

# JSON integers only: lax mode would turn true into 1 and "30" into 30 (decision M3.6).
CheckInterval = Annotated[
    int, Strict(), Field(ge=CHECK_INTERVAL_SECONDS.low, le=CHECK_INTERVAL_SECONDS.high)
]
CheckTimeout = Annotated[
    int, Strict(), Field(ge=CHECK_TIMEOUT_SECONDS.low, le=CHECK_TIMEOUT_SECONDS.high)
]
FailuresBeforeDown = Annotated[
    int, Strict(), Field(ge=FAILURES_BEFORE_DOWN.low, le=FAILURES_BEFORE_DOWN.high)
]
RetentionDays = Annotated[int, Strict(), Field(ge=RETENTION_DAYS.low, le=RETENTION_DAYS.high)]


class SettingsOut(BaseModel):
    """The settings in effect: stored values, or the defaults for values never changed."""

    check_interval_seconds: int
    check_timeout_seconds: int
    failures_before_down: int
    retention_days: int


class SettingsUpdate(RequestModel):
    """Partial update: fields left out stay unchanged; null is not allowed.

    The timeout must be at most half the interval, so a check always ends well before the
    next round (brief section 4).
    """

    check_interval_seconds: CheckInterval = omittable()
    check_timeout_seconds: CheckTimeout = omittable()
    failures_before_down: FailuresBeforeDown = omittable()
    retention_days: RetentionDays = omittable()
