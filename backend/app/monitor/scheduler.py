"""The status monitor: an asyncio task started with the app (brief section 4).

Exactly one runs, because NetScope runs exactly one uvicorn worker. It is never called from
a request handler; it reads and writes the database only through the services layer, in a
worker thread (SQLAlchemy is sync).

How it runs:

- **Rounds.** Every check interval, every device whose check is on is checked. Rounds never
  overlap: one that takes longer than the interval is followed by the next right away. At
  most ``MAX_CONCURRENT_CHECKS`` checks run at once, each limited to the check timeout (at
  most half the interval). One round's results are written in one transaction.
- **New checks.** Between rounds the monitor looks every ``TICK_SECONDS`` for checks without
  a result yet (turned on or changed; changing a check resets its status) and checks those
  right away. Settings changes take effect at the same moment.
- **Purge.** A second task deletes history older than the retention every hour, starting a
  minute after startup, in short batches with pauses (``services.status.purge_history``).
- An error in a round or a purge is logged and the monitor carries on.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.timeutil import utcnow
from app.models import DeviceStatus
from app.monitor.checks import Checker, CheckOutcome, prepare, run_check
from app.services import app_settings as settings_service
from app.services import status as status_service
from app.services.app_settings import AppSettings
from app.services.status import CheckJob, CheckResult, Transition

logger = logging.getLogger("netscope.monitor")

MAX_CONCURRENT_CHECKS = 50  # owner decision, M6
TICK_SECONDS = 5.0
PURGE_FIRST_DELAY_SECONDS = 60.0
PURGE_EVERY_SECONDS = 3600.0
PURGE_BATCH_SIZE = 5000  # about 60 ms per batch (measured, M6)
PURGE_PAUSE_SECONDS = 0.2
STOP_TIMEOUT_SECONDS = 10.0


class Monitor:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        checker: Checker = run_check,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._session_factory = session_factory
        self._checker = checker
        self._clock = clock
        # Read here, not as default arguments, so tests can shorten them.
        self._tick = TICK_SECONDS
        self._purge_first_delay = PURGE_FIRST_DELAY_SECONDS
        self._purge_every = PURGE_EVERY_SECONDS
        self._tasks: list[asyncio.Task[None]] = []
        # The monitor's own database thread: name lookups use asyncio's default threads, and
        # lookups that hang past their timeout must not hold up the writes (M6 review).
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="netscope-monitor-db")
        # Database calls still running in their thread (they cannot be cancelled).
        self._db_calls: set[asyncio.Future[Any]] = set()
        self._last_round: float | None = None
        # When the check loop last finished a step (a round, or the checks of new devices),
        # or started: the dashboard warns when this gets old (owner decision, M8).
        self._last_progress: float = clock()

    def seconds_since_progress(self) -> float:
        return max(0.0, self._clock() - self._last_progress)

    # --- Lifecycle -----------------------------------------------------------------------

    def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._check_loop(), name="netscope-status-checks"),
            asyncio.create_task(self._purge_loop(), name="netscope-status-purge"),
        ]
        logger.info("Status monitor started.")

    async def stop(self) -> None:
        """Cancel the loops and running checks; wait for a database write in progress, so the
        engine is not closed under it."""
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        if self._db_calls:
            await asyncio.wait(self._db_calls, timeout=STOP_TIMEOUT_SECONDS)
        self._executor.shutdown(wait=False)

    # --- Loops ---------------------------------------------------------------------------

    async def _check_loop(self) -> None:
        try:
            await asyncio.to_thread(prepare)
        except Exception:  # checks still work; the first HTTPS one makes them itself
            logger.exception("Preparing the TLS settings for HTTPS checks failed.")
        while True:
            try:
                settings = await self._db(settings_service.get_settings)
                await self.tick(settings)
                self._last_progress = self._clock()
                wait = self._seconds_to_next_round(settings)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Status checks failed; trying again shortly.")
                wait = self._tick
            await asyncio.sleep(min(self._tick, wait))

    async def _purge_loop(self) -> None:
        await asyncio.sleep(self._purge_first_delay)
        while True:
            try:
                settings = await self._db(settings_service.get_settings)
                await self.purge(settings)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Purging old status history failed; trying again later.")
            await asyncio.sleep(self._purge_every)

    # --- One step ------------------------------------------------------------------------

    async def tick(self, settings: AppSettings) -> None:
        """A full round when one is due, else the checks without a result yet."""
        now = self._clock()
        if self._seconds_to_next_round(settings, now) <= 0:
            self._last_round = now
            await self.run_round(settings)
        else:
            await self.run_round(settings, only_new=True)

    def _seconds_to_next_round(self, settings: AppSettings, now: float | None = None) -> float:
        if self._last_round is None:
            return 0.0
        now = self._clock() if now is None else now
        return self._last_round + settings.check_interval_seconds - now

    async def run_round(self, settings: AppSettings, *, only_new: bool = False) -> None:
        jobs = await self._db(status_service.checks_to_run, only_new=only_new)
        if not jobs:
            return
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)
        timeout = settings.check_timeout_seconds

        async def check(job: CheckJob) -> tuple[CheckJob, CheckResult]:
            async with semaphore:
                outcome = await self.check_one(job, timeout)
            result = CheckResult(
                is_up=outcome.is_up,
                latency_ms=outcome.latency_ms,
                error=outcome.error,
                checked_at=utcnow(),
            )
            return job, result

        results = await asyncio.gather(*(check(job) for job in jobs))
        transitions = await self._db(
            status_service.record_results, results, settings.failures_before_down
        )
        for transition in transitions:
            _log_transition(transition)

    async def check_one(self, job: CheckJob, timeout: float) -> CheckOutcome:
        """The job's check within ``timeout`` seconds. Never raises (except when cancelled)."""
        try:
            async with asyncio.timeout(timeout):
                return await self._checker(job, timeout)
        except TimeoutError:
            return CheckOutcome(is_up=False, error=f"Timed out after {timeout:g} s")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("The status check of %s failed unexpectedly.", job.name)
            return CheckOutcome(is_up=False, error="The check failed unexpectedly (see the log).")

    async def purge(self, settings: AppSettings) -> int:
        """Delete history older than the retention, in batches. Returns how many rows."""
        older_than = utcnow() - timedelta(days=settings.retention_days)
        total = 0
        while True:
            deleted = await self._db(
                status_service.purge_history, older_than, batch_size=PURGE_BATCH_SIZE
            )
            total += deleted
            if deleted < PURGE_BATCH_SIZE:
                break
            await asyncio.sleep(PURGE_PAUSE_SECONDS)  # let other writes in
        if total:
            logger.info(
                "Deleted %d status checks older than %d days.", total, settings.retention_days
            )
        return total

    # --- Database ------------------------------------------------------------------------

    async def _db[T](self, function: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run a services call with its own session in the monitor's database thread.

        The thread cannot be stopped once it runs, so the call is shielded from cancellation
        and remembered: ``stop`` waits for it before the engine is closed.
        """

        def call() -> T:
            with self._session_factory() as db:
                return function(db, *args, **kwargs)

        future = asyncio.get_running_loop().run_in_executor(self._executor, call)
        self._db_calls.add(future)
        future.add_done_callback(self._db_calls.discard)
        return await asyncio.shield(future)


def _log_transition(transition: Transition) -> None:
    if transition.status == DeviceStatus.DOWN:
        logger.info("%s is down: %s", transition.name, transition.error)
    else:
        logger.info("%s is up again.", transition.name)
