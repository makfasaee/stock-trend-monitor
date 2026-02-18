"""Pipeline coordinator — wires together fetch → compute → store → deliver."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

import pandas_market_calendars as mcal

from stockwatch.config import Config
from stockwatch.delivery.cli_output import print_digest
from stockwatch.delivery.email_sender import send_digest_email
from stockwatch.delivery.file_writer import write_artifacts
from stockwatch.delivery.x_poster import post_digest_tweet
from stockwatch.digest import DigestData
from stockwatch.providers.base import DataProvider, ProviderError
from stockwatch.storage import repository
from stockwatch.trend import classify
from stockwatch.utils.logging import get_logger
from stockwatch.utils.retry import retry_on_provider_error

log = get_logger(__name__)


def _is_market_open(run_date: date, calendar_name: str) -> bool:
    cal = mcal.get_calendar(calendar_name)
    schedule = cal.schedule(
        start_date=run_date.isoformat(),
        end_date=run_date.isoformat(),
    )
    return not schedule.empty


def _fetch_range_for_ticker(
    ticker: str,
    conn: sqlite3.Connection,
    provider: DataProvider,
    backfill_days: int,
) -> int:
    """Determine fetch window and upsert prices.  Returns row count."""
    max_date = repository.get_max_price_date(conn, ticker)
    today = date.today()

    if max_date is None:
        start = today - timedelta(days=backfill_days)
    else:
        start = max_date + timedelta(days=1)

    if start > today:
        log.debug("ticker_up_to_date", ticker=ticker)
        return 0

    @retry_on_provider_error
    def _fetch() -> list:
        return provider.fetch_ohlcv(ticker, start, today)

    try:
        rows = _fetch()
    except ProviderError as exc:
        log.error("fetch_failed_skipping", ticker=ticker, error=str(exc))
        return 0

    return repository.upsert_prices(conn, rows)


def _compute_indicators_for_ticker(
    ticker: str,
    conn: sqlite3.Connection,
    run_date: date,
    config: Config,
) -> bool:
    """Compute and store indicators for *ticker* on *run_date*.

    Returns True if indicators were stored, False if insufficient data.
    """
    series = repository.get_adj_close_series(conn, ticker, limit=300)
    if not series:
        return False

    prices = [row[1] for row in series]
    volumes = [row[2] for row in series]

    result = classify(
        prices,
        volumes,
        uptrend_min=config.uptrend_min,
        downtrend_max=config.downtrend_max,
        volume_anomaly_multiplier=config.volume_anomaly_multiplier,
    )

    record = {
        "ticker": ticker,
        "date": run_date.isoformat(),
        "ma20": result.ma20,
        "ma50": result.ma50,
        "rsi14": result.rsi14,
        "return_1d": result.return_1d,
        "return_5d": result.return_5d,
        "return_20d": result.return_20d,
        "volatility_20d": result.volatility_20d,
        "volume_anomaly": int(result.volume_anomaly),
        "trend": result.label,
        "trend_strength": result.strength,
    }
    repository.upsert_indicator(conn, record)
    return True


def run_daily_pipeline(
    config: Config,
    conn: sqlite3.Connection,
    provider: DataProvider,
    run_date: date | None = None,
    reports_dir: str = "reports",
) -> None:
    """Execute the full daily pipeline for all configured tickers."""
    if run_date is None:
        run_date = date.today()

    log.info("pipeline_start", run_date=run_date.isoformat())

    # ── Holiday guard ─────────────────────────────────────────────────────────
    if not _is_market_open(run_date, config.market_calendar):
        log.info("market_closed_skipping", run_date=run_date.isoformat())
        return

    # ── Fetch prices ──────────────────────────────────────────────────────────
    total_rows = 0
    for ticker in config.tickers:
        n = _fetch_range_for_ticker(ticker, conn, provider, config.backfill_days)
        total_rows += n
    log.info("prices_fetched", total_rows=total_rows)

    # ── Compute indicators ────────────────────────────────────────────────────
    computed = 0
    for ticker in config.tickers:
        if _compute_indicators_for_ticker(ticker, conn, run_date, config):
            computed += 1
    log.info("indicators_computed", count=computed)

    # ── Build digest ──────────────────────────────────────────────────────────
    indicators = repository.get_indicators_for_date(conn, run_date)
    digest = DigestData(run_date=run_date, indicators=indicators).build(
        top_n=config.top_movers_count
    )

    # ── Write files ───────────────────────────────────────────────────────────
    json_path, md_path = write_artifacts(digest, reports_dir)
    log.info("artifacts_written", json=json_path, markdown=md_path)

    # ── Store report ──────────────────────────────────────────────────────────
    report_record = {
        "run_date": run_date.isoformat(),
        "ticker_count": digest.total,
        "uptrend_count": digest.uptrend_count,
        "downtrend_count": digest.downtrend_count,
        "sideways_count": digest.sideways_count,
        "top_movers_json": digest.top_movers_dict(),
        "summary_text": digest.render_email_text(),
        "summary_html": None,
        "markdown_path": md_path,
        "json_path": json_path,
        "llm_used": 0,
    }
    report_id = repository.insert_report(conn, report_record)
    log.info("report_stored", report_id=report_id)

    # ── CLI output ────────────────────────────────────────────────────────────
    print_digest(digest)

    # ── Email ─────────────────────────────────────────────────────────────────
    if config.enable_email and config.ses_from_address and config.ses_recipient_addresses:
        send_digest_email(
            d=digest,
            report_id=report_id,
            conn=conn,
            from_address=config.ses_from_address,
            recipient_addresses=config.ses_recipient_addresses,
            aws_region=config.aws_region,
            dry_run=config.dry_run,
        )

    # ── X (Twitter) ───────────────────────────────────────────────────────────
    if config.enable_twitter and config.twitter_api_key:
        post_digest_tweet(
            d=digest,
            report_id=report_id,
            conn=conn,
            api_key=config.twitter_api_key,
            api_secret=config.twitter_api_secret,
            access_token=config.twitter_access_token,
            access_token_secret=config.twitter_access_token_secret,
            bearer_token=config.twitter_bearer_token,
            max_chars=config.max_tweet_chars,
            dry_run=config.dry_run,
        )

    log.info("pipeline_complete", run_date=run_date.isoformat())
