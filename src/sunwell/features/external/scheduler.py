"""External Scheduler for Scheduled Events (RFC-049).

Cron-based scheduler for periodic events like nightly backlog runs.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sunwell.features.external.types import EventSource, EventType, ExternalEvent

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from sunwell.features.external.processor import EventProcessor

logger = logging.getLogger(__name__)


class ExternalScheduler:
    """Schedule external events on cron patterns.

    Uses APScheduler for cron-based scheduling.
    """

    def __init__(self, processor: EventProcessor):
        """Initialize scheduler.

        Args:
            processor: Event processor to handle scheduled events
        """
        self.processor = processor
        self._scheduler = None
        self._jobs: dict[str, dict] = {}

    def _get_scheduler(self) -> AsyncIOScheduler | None:
        """Get or create APScheduler instance."""
        if self._scheduler is None:
            try:
                from apscheduler.schedulers.asyncio import AsyncIOScheduler

                self._scheduler = AsyncIOScheduler()
            except ImportError:
                logger.warning("APScheduler not available - scheduled jobs disabled")
        return self._scheduler

    def add_cron_job(
        self,
        name: str,
        cron_expression: str,
        event_factory: Callable[[], ExternalEvent],
    ) -> None:
        """Add a scheduled job.

        Args:
            name: Job identifier
            cron_expression: Cron pattern (e.g., "0 0 * * *" for midnight)
            event_factory: Function that creates the event to process
        """
        scheduler = self._get_scheduler()
        if not scheduler:
            logger.warning(f"Cannot add job {name}: scheduler not available")
            return

        try:
            from apscheduler.triggers.cron import CronTrigger

            trigger = CronTrigger.from_crontab(cron_expression)

            async def job() -> None:
                logger.info(f"Running scheduled job: {name}")
                event = event_factory()
                await self.processor.process_event(event)

            scheduler.add_job(
                job,
                trigger=trigger,
                id=name,
                name=name,
                replace_existing=True,
            )

            self._jobs[name] = {
                "cron": cron_expression,
                "enabled": True,
            }

            logger.info(f"Added scheduled job: {name} ({cron_expression})")

        except Exception as e:
            logger.error(f"Error adding job {name}: {e}")

    def add_default_schedules(self) -> None:
        """Add default scheduled jobs."""
        # Nightly backlog refresh
        self.add_cron_job(
            name="nightly_backlog",
            cron_expression="0 0 * * *",  # Midnight
            event_factory=lambda: ExternalEvent(
                id=f"cron-nightly-{datetime.now().date()}",
                source=EventSource.CRON,
                event_type=EventType.CRON_TRIGGER,
                timestamp=datetime.now(UTC),
                data={"trigger": "nightly_backlog"},
                external_ref=f"cron:nightly:{datetime.now().date()}",
            ),
        )

        # Dependency security check (weekly on Monday 9am)
        self.add_cron_job(
            name="weekly_security",
            cron_expression="0 9 * * 1",  # Monday 9am
            event_factory=lambda: ExternalEvent(
                id=f"cron-security-{datetime.now().isocalendar().week}",
                source=EventSource.CRON,
                event_type=EventType.CRON_TRIGGER,
                timestamp=datetime.now(UTC),
                data={"trigger": "security_scan"},
                external_ref=f"cron:security:{datetime.now().year}-W{datetime.now().isocalendar().week}",
            ),
        )

        # WAL compaction (daily at 3am)
        self.add_cron_job(
            name="wal_compaction",
            cron_expression="0 3 * * *",  # 3am
            event_factory=lambda: ExternalEvent(
                id=f"cron-compact-{datetime.now().date()}",
                source=EventSource.CRON,
                event_type=EventType.CRON_TRIGGER,
                timestamp=datetime.now(UTC),
                data={"trigger": "wal_compaction"},
                external_ref=f"cron:compact:{datetime.now().date()}",
            ),
        )

    def remove_job(self, name: str) -> bool:
        """Remove a scheduled job.

        Args:
            name: Job identifier

        Returns:
            True if job was removed
        """
        scheduler = self._get_scheduler()
        if not scheduler:
            return False

        try:
            scheduler.remove_job(name)
            self._jobs.pop(name, None)
            logger.info(f"Removed scheduled job: {name}")
            return True
        except Exception:
            return False

    def start(self) -> None:
        """Start the scheduler."""
        scheduler = self._get_scheduler()
        if scheduler and not scheduler.running:
            scheduler.start()
            logger.info("External scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("External scheduler stopped")

    def get_jobs(self) -> list[dict]:
        """Get list of scheduled jobs.

        Returns:
            List of job info dictionaries
        """
        scheduler = self._get_scheduler()
        if not scheduler:
            return []

        jobs = []
        for job in scheduler.get_jobs():
            job_info = self._jobs.get(job.id, {})
            jobs.append({
                "id": job.id,
                "name": job.name,
                "cron": job_info.get("cron", "unknown"),
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "enabled": job_info.get("enabled", True),
            })

        return jobs

    async def run_job_now(self, name: str) -> bool:
        """Run a scheduled job immediately.

        Args:
            name: Job identifier

        Returns:
            True if job was triggered
        """
        scheduler = self._get_scheduler()
        if not scheduler:
            return False

        try:
            job = scheduler.get_job(name)
            if job:
                await job.func()
                return True
        except Exception as e:
            logger.error(f"Error running job {name}: {e}")

        return False
