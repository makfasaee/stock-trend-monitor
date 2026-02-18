"""All SQL interactions — no raw SQL outside this module."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from typing import Any

from stockwatch.providers.base import OHLCVRow


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Prices ────────────────────────────────────────────────────────────────────

def upsert_prices(conn: sqlite3.Connection, rows: list[OHLCVRow]) -> int:
    """Upsert a batch of OHLCV rows.  Returns the number of rows processed."""
    if not rows:
        return 0
    fetched_at = _utcnow()
    conn.executemany(
        """
        INSERT INTO prices (ticker, date, open, high, low, close, adj_close, volume, fetched_at, source)
        VALUES (:ticker, :date, :open, :high, :low, :close, :adj_close, :volume, :fetched_at, :source)
        ON CONFLICT(ticker, date) DO UPDATE SET
            close=excluded.close,
            adj_close=excluded.adj_close,
            volume=excluded.volume,
            fetched_at=excluded.fetched_at
        """,
        [
            {
                "ticker": r.ticker,
                "date": r.date.isoformat(),
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "adj_close": r.adj_close,
                "volume": r.volume,
                "fetched_at": fetched_at,
                "source": r.source,
            }
            for r in rows
        ],
    )
    conn.commit()
    return len(rows)


def get_max_price_date(conn: sqlite3.Connection, ticker: str) -> date | None:
    """Return the most recent date we have prices for *ticker*, or None."""
    row = conn.execute(
        "SELECT MAX(date) AS max_date FROM prices WHERE ticker = ?", (ticker,)
    ).fetchone()
    if row and row["max_date"]:
        return date.fromisoformat(row["max_date"])
    return None


def get_adj_close_series(
    conn: sqlite3.Connection, ticker: str, limit: int = 300
) -> list[tuple[date, float, int]]:
    """Return (date, adj_close, volume) tuples for *ticker*, most-recent last."""
    rows = conn.execute(
        """
        SELECT date, adj_close, volume
        FROM prices
        WHERE ticker = ?
        ORDER BY date ASC
        LIMIT ?
        """,
        (ticker, limit),
    ).fetchall()
    return [(date.fromisoformat(r["date"]), r["adj_close"], r["volume"]) for r in rows]


# ── Indicators ────────────────────────────────────────────────────────────────

def upsert_indicator(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    """Insert or replace an indicators row for (ticker, date)."""
    record = dict(record)
    record.setdefault("computed_at", _utcnow())
    conn.execute(
        """
        INSERT INTO indicators
            (ticker, date, ma20, ma50, rsi14, return_1d, return_5d, return_20d,
             volatility_20d, volume_anomaly, trend, trend_strength, computed_at)
        VALUES
            (:ticker, :date, :ma20, :ma50, :rsi14, :return_1d, :return_5d, :return_20d,
             :volatility_20d, :volume_anomaly, :trend, :trend_strength, :computed_at)
        ON CONFLICT(ticker, date) DO UPDATE SET
            ma20=excluded.ma20, ma50=excluded.ma50, rsi14=excluded.rsi14,
            return_1d=excluded.return_1d, return_5d=excluded.return_5d,
            return_20d=excluded.return_20d, volatility_20d=excluded.volatility_20d,
            volume_anomaly=excluded.volume_anomaly, trend=excluded.trend,
            trend_strength=excluded.trend_strength, computed_at=excluded.computed_at
        """,
        record,
    )
    conn.commit()


def get_indicators_for_date(
    conn: sqlite3.Connection, run_date: date
) -> list[dict[str, Any]]:
    """Return all indicator rows for a given run date."""
    rows = conn.execute(
        "SELECT * FROM indicators WHERE date = ?", (run_date.isoformat(),)
    ).fetchall()
    return [dict(r) for r in rows]


# ── Reports ───────────────────────────────────────────────────────────────────

def insert_report(conn: sqlite3.Connection, record: dict[str, Any]) -> int:
    """Insert a report row and return its id.  Raises IntegrityError on dup run_date."""
    record = dict(record)
    record.setdefault("generated_at", _utcnow())
    if "top_movers_json" in record and not isinstance(record["top_movers_json"], str):
        record["top_movers_json"] = json.dumps(record["top_movers_json"])
    cursor = conn.execute(
        """
        INSERT OR REPLACE INTO reports
            (run_date, generated_at, ticker_count, uptrend_count, downtrend_count,
             sideways_count, top_movers_json, summary_text, summary_html,
             markdown_path, json_path, llm_used)
        VALUES
            (:run_date, :generated_at, :ticker_count, :uptrend_count, :downtrend_count,
             :sideways_count, :top_movers_json, :summary_text, :summary_html,
             :markdown_path, :json_path, :llm_used)
        """,
        record,
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


def get_report_by_date(conn: sqlite3.Connection, run_date: date) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM reports WHERE run_date = ?", (run_date.isoformat(),)
    ).fetchone()
    return dict(row) if row else None


# ── Email logs ────────────────────────────────────────────────────────────────

def insert_email_log(conn: sqlite3.Connection, record: dict[str, Any]) -> int:
    record = dict(record)
    record.setdefault("sent_at", _utcnow())
    if "recipients_json" in record and not isinstance(record["recipients_json"], str):
        record["recipients_json"] = json.dumps(record["recipients_json"])
    cursor = conn.execute(
        """
        INSERT INTO email_logs
            (report_id, sent_at, recipients_json, subject, ses_message_id,
             status, error_message, attempt_number)
        VALUES
            (:report_id, :sent_at, :recipients_json, :subject, :ses_message_id,
             :status, :error_message, :attempt_number)
        """,
        record,
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


# ── Tweet logs ────────────────────────────────────────────────────────────────

def has_tweet_for_date(conn: sqlite3.Connection, run_date: date) -> bool:
    """Return True if a tweet was already posted for this market day."""
    row = conn.execute(
        "SELECT 1 FROM tweet_logs WHERE run_date = ? AND status = 'posted'",
        (run_date.isoformat(),),
    ).fetchone()
    return row is not None


def insert_tweet_log(conn: sqlite3.Connection, record: dict[str, Any]) -> int:
    record = dict(record)
    record.setdefault("posted_at", _utcnow())
    if "response_json" in record and not isinstance(record["response_json"], str):
        record["response_json"] = json.dumps(record["response_json"])
    cursor = conn.execute(
        """
        INSERT INTO tweet_logs
            (report_id, posted_at, run_date, payload_text, response_json,
             tweet_id, status, error_message, attempt_number)
        VALUES
            (:report_id, :posted_at, :run_date, :payload_text, :response_json,
             :tweet_id, :status, :error_message, :attempt_number)
        """,
        record,
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]
