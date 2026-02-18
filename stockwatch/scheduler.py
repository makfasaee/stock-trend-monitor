"""APScheduler setup — runs the daily pipeline on a cron schedule."""

from __future__ import annotations

import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from stockwatch.config import Config
from stockwatch.orchestrator import run_daily_pipeline
from stockwatch.providers.yfinance_provider import YFinanceProvider
from stockwatch.storage.db import init_db
from stockwatch.utils.logging import get_logger

log = get_logger(__name__)


def _make_job(config: Config) -> None:
    """Create a fresh DB connection and run the pipeline (called by APScheduler)."""
    conn = init_db(config.db_path)
    provider = YFinanceProvider()
    try:
        run_daily_pipeline(config=config, conn=conn, provider=provider)
    finally:
        conn.close()


def start_scheduler(config: Config) -> None:
    """Start the blocking APScheduler process."""
    scheduler = BlockingScheduler(timezone=config.run_timezone)

    trigger = CronTrigger(
        day_of_week="mon-fri",
        hour=config.run_hour,
        minute=config.run_minute,
        timezone=config.run_timezone,
    )

    scheduler.add_job(
        _make_job,
        trigger=trigger,
        args=[config],
        id="daily_digest",
        name="StockWatch Daily Digest",
        misfire_grace_time=config.misfire_grace_seconds,
        coalesce=True,
        max_instances=1,
    )

    def _shutdown(signum: int, frame: object) -> None:
        log.info("scheduler_shutdown_signal", signum=signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info(
        "scheduler_started",
        hour=config.run_hour,
        minute=config.run_minute,
        tz=config.run_timezone,
    )
    scheduler.start()
