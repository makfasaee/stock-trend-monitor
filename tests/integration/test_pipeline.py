"""Integration tests for the full pipeline — in-memory SQLite, mock provider."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import sqlite3
import tempfile

import pytest
from freezegun import freeze_time

from stockwatch.config import Config, reset_config
from stockwatch.orchestrator import run_daily_pipeline, _fetch_range_for_ticker
from stockwatch.storage import repository
from stockwatch.storage.db import init_db
from tests.conftest import MockDataProvider


@pytest.fixture()
def cfg(tmp_path: Path) -> Config:
    """Minimal Config with 2 tickers, pointing at a temp settings.toml."""
    toml_content = """
[watchlist]
tickers = ["AAPL", "MSFT"]

[thresholds]
uptrend_min = 62.0
downtrend_max = 38.0
volume_anomaly_multiplier = 2.0
top_movers_count = 5

[indicators]
ma_short = 20
ma_long = 50
rsi_period = 14
return_periods = [1, 5, 20]
volatility_period = 20
backfill_days = 252

[scheduling]
run_hour = 16
run_minute = 30
run_timezone = "America/New_York"
market_calendar = "NYSE"
misfire_grace_seconds = 3600

[digest]
max_tweet_chars = 280
top_movers_count = 5

[healthcheck]
port = 8080
host = "0.0.0.0"

[logging]
level = "INFO"
format = "json"
"""
    cfg_path = tmp_path / "settings.toml"
    cfg_path.write_text(toml_content)
    reset_config()
    config = Config(cfg_path)
    config.db_path = ":memory:"
    config.enable_email = False
    config.enable_twitter = False
    config.dry_run = True
    return config


@pytest.fixture()
def pipeline_db() -> sqlite3.Connection:
    return init_db(":memory:")


# We freeze to a known NYSE trading day (Wed 2024-03-27)
TRADE_DATE = date(2024, 3, 27)


@freeze_time("2024-03-27")
def test_full_run_populates_tables(cfg: Config, pipeline_db: sqlite3.Connection) -> None:
    provider = MockDataProvider()
    run_daily_pipeline(config=cfg, conn=pipeline_db, provider=provider, run_date=TRADE_DATE)

    # Prices should be loaded
    price_count = pipeline_db.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    assert price_count > 0

    # Indicators computed for both tickers
    ind_count = pipeline_db.execute(
        "SELECT COUNT(*) FROM indicators WHERE date = ?", (TRADE_DATE.isoformat(),)
    ).fetchone()[0]
    assert ind_count == 2

    # One report row
    report_count = pipeline_db.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    assert report_count == 1


@freeze_time("2024-03-27")
def test_incremental_fetch(cfg: Config, pipeline_db: sqlite3.Connection) -> None:
    """Second run should not refetch historical data."""
    provider = MockDataProvider()
    # First run
    run_daily_pipeline(config=cfg, conn=pipeline_db, provider=provider, run_date=TRADE_DATE)
    first_count = pipeline_db.execute("SELECT COUNT(*) FROM prices").fetchone()[0]

    # Second run on same date
    run_daily_pipeline(config=cfg, conn=pipeline_db, provider=provider, run_date=TRADE_DATE)
    second_count = pipeline_db.execute("SELECT COUNT(*) FROM prices").fetchone()[0]

    # Idempotent — no extra rows added
    assert second_count == first_count


@freeze_time("2024-03-27")
def test_idempotency_report_unique(cfg: Config, pipeline_db: sqlite3.Connection) -> None:
    """Running the pipeline twice for the same date produces only 1 report row."""
    provider = MockDataProvider()
    run_daily_pipeline(config=cfg, conn=pipeline_db, provider=provider, run_date=TRADE_DATE)
    run_daily_pipeline(config=cfg, conn=pipeline_db, provider=provider, run_date=TRADE_DATE)

    count = pipeline_db.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    assert count == 1


@freeze_time("2024-12-25")  # Christmas — NYSE closed
def test_market_holiday_exits_early(cfg: Config, pipeline_db: sqlite3.Connection) -> None:
    provider = MockDataProvider()
    run_daily_pipeline(config=cfg, conn=pipeline_db, provider=provider, run_date=date(2024, 12, 25))

    report_count = pipeline_db.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    assert report_count == 0


@freeze_time("2024-03-27")
def test_provider_error_skips_ticker_pipeline_continues(
    cfg: Config, pipeline_db: sqlite3.Connection
) -> None:
    """If one ticker raises ProviderError, the pipeline continues for the rest."""
    provider = MockDataProvider(error_tickers={"AAPL"})
    run_daily_pipeline(config=cfg, conn=pipeline_db, provider=provider, run_date=TRADE_DATE)

    # MSFT should still have data
    msft_count = pipeline_db.execute(
        "SELECT COUNT(*) FROM prices WHERE ticker = 'MSFT'"
    ).fetchone()[0]
    assert msft_count > 0

    # AAPL has no data (error skipped)
    aapl_count = pipeline_db.execute(
        "SELECT COUNT(*) FROM prices WHERE ticker = 'AAPL'"
    ).fetchone()[0]
    assert aapl_count == 0
