"""CLI entry point: python -m stockwatch <command>

Commands:
  run       Run the pipeline once for today (or --date YYYY-MM-DD).
  backfill  Backfill historical prices for all tickers.
  status    Print last report summary and DB stats.
  migrate   Initialize / migrate the database schema.
  scheduler Start the blocking APScheduler process.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from stockwatch.config import get_config
from stockwatch.storage.db import init_db
from stockwatch.utils.logging import configure_logging, get_logger


def _cmd_migrate(args: argparse.Namespace) -> None:
    config = get_config()
    configure_logging(config.log_level)
    conn = init_db(config.db_path)
    conn.close()
    print(f"Database ready at {config.db_path}")


def _cmd_run(args: argparse.Namespace) -> None:
    config = get_config()
    configure_logging(config.log_level)
    log = get_logger()

    from stockwatch.orchestrator import run_daily_pipeline
    from stockwatch.providers.yfinance_provider import YFinanceProvider

    run_date = date.fromisoformat(args.date) if args.date else None
    conn = init_db(config.db_path)
    provider = YFinanceProvider()
    try:
        run_daily_pipeline(
            config=config,
            conn=conn,
            provider=provider,
            run_date=run_date,
        )
    finally:
        conn.close()


def _cmd_backfill(args: argparse.Namespace) -> None:
    """Alias for run — the orchestrator already handles incremental/full backfill."""
    config = get_config()
    configure_logging(config.log_level)

    from stockwatch.orchestrator import _fetch_range_for_ticker
    from stockwatch.providers.yfinance_provider import YFinanceProvider
    from stockwatch.storage import repository

    conn = init_db(config.db_path)
    provider = YFinanceProvider()
    total = 0
    for ticker in config.tickers:
        n = _fetch_range_for_ticker(ticker, conn, provider, config.backfill_days)
        total += n
        print(f"  {ticker}: {n} rows")
    conn.close()
    print(f"\nBackfill complete. {total} total rows upserted.")


def _cmd_status(args: argparse.Namespace) -> None:
    config = get_config()
    configure_logging(config.log_level)

    import sqlite3
    from pathlib import Path

    db = Path(config.db_path)
    if not db.exists():
        print("Database not found. Run 'migrate' first.")
        sys.exit(1)

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row

    row = conn.execute("SELECT * FROM reports ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        print("No reports yet.")
    else:
        print(f"Last run date    : {row['run_date']}")
        print(f"Generated at     : {row['generated_at']}")
        print(f"Tickers          : {row['ticker_count']}")
        print(f"  Uptrend        : {row['uptrend_count']}")
        print(f"  Downtrend      : {row['downtrend_count']}")
        print(f"  Sideways       : {row['sideways_count']}")

    count = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    size = db.stat().st_size
    print(f"\nTotal reports    : {count}")
    print(f"DB size          : {size:,} bytes")
    conn.close()


def _cmd_scheduler(args: argparse.Namespace) -> None:
    config = get_config()
    configure_logging(config.log_level)
    init_db(config.db_path).close()

    from stockwatch.utils.healthcheck import start_healthcheck_server
    start_healthcheck_server(
        host=config.healthcheck_host,
        port=config.healthcheck_port,
        db_path=config.db_path,
    )

    from stockwatch.scheduler import start_scheduler
    start_scheduler(config)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="stockwatch",
        description="Daily stock trend monitor",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # migrate
    sub.add_parser("migrate", help="Initialize / migrate the database schema")

    # run
    p_run = sub.add_parser("run", help="Run the pipeline once")
    p_run.add_argument("--date", help="Override run date (YYYY-MM-DD)", default=None)

    # backfill
    sub.add_parser("backfill", help="Backfill historical prices for all tickers")

    # status
    sub.add_parser("status", help="Show last report and DB stats")

    # scheduler
    sub.add_parser("scheduler", help="Start the APScheduler daemon")

    args = parser.parse_args()

    dispatch = {
        "migrate": _cmd_migrate,
        "run": _cmd_run,
        "backfill": _cmd_backfill,
        "status": _cmd_status,
        "scheduler": _cmd_scheduler,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
