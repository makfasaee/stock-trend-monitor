"""SQLite connection management, WAL mode, and schema migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path


_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS prices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT    NOT NULL,
    date        TEXT    NOT NULL,
    open        REAL    NOT NULL,
    high        REAL    NOT NULL,
    low         REAL    NOT NULL,
    close       REAL    NOT NULL,
    adj_close   REAL    NOT NULL,
    volume      INTEGER NOT NULL,
    fetched_at  TEXT    NOT NULL,
    source      TEXT    NOT NULL DEFAULT 'yfinance',
    UNIQUE(ticker, date)
);
CREATE INDEX IF NOT EXISTS idx_prices_ticker_date ON prices(ticker, date DESC);

CREATE TABLE IF NOT EXISTS indicators (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT    NOT NULL,
    date            TEXT    NOT NULL,
    ma20            REAL,
    ma50            REAL,
    rsi14           REAL,
    return_1d       REAL,
    return_5d       REAL,
    return_20d      REAL,
    volatility_20d  REAL,
    volume_anomaly  INTEGER NOT NULL DEFAULT 0,
    trend           TEXT    NOT NULL,
    trend_strength  REAL    NOT NULL,
    computed_at     TEXT    NOT NULL,
    UNIQUE(ticker, date),
    FOREIGN KEY (ticker, date) REFERENCES prices(ticker, date) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date        TEXT    NOT NULL UNIQUE,
    generated_at    TEXT    NOT NULL,
    ticker_count    INTEGER NOT NULL,
    uptrend_count   INTEGER NOT NULL,
    downtrend_count INTEGER NOT NULL,
    sideways_count  INTEGER NOT NULL,
    top_movers_json TEXT    NOT NULL,
    summary_text    TEXT,
    summary_html    TEXT,
    markdown_path   TEXT,
    json_path       TEXT,
    llm_used        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS email_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id       INTEGER NOT NULL REFERENCES reports(id),
    sent_at         TEXT    NOT NULL,
    recipients_json TEXT    NOT NULL,
    subject         TEXT    NOT NULL,
    ses_message_id  TEXT,
    status          TEXT    NOT NULL,
    error_message   TEXT,
    attempt_number  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tweet_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id       INTEGER NOT NULL REFERENCES reports(id),
    posted_at       TEXT    NOT NULL,
    run_date        TEXT    NOT NULL UNIQUE,
    payload_text    TEXT    NOT NULL,
    response_json   TEXT,
    tweet_id        TEXT,
    status          TEXT    NOT NULL,
    error_message   TEXT,
    attempt_number  INTEGER NOT NULL DEFAULT 1
);
"""


def get_connection(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """Return a sqlite3 connection with WAL mode and foreign keys enabled.

    Using ``check_same_thread=False`` is safe here because all writes are
    funnelled through the repository layer which is called synchronously from
    the orchestrator.
    """
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def run_migrations(conn: sqlite3.Connection) -> None:
    """Apply the DDL (idempotent — uses CREATE IF NOT EXISTS)."""
    conn.executescript(_DDL)
    conn.commit()


def init_db(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open (or create) the database and run migrations.  Returns the connection."""
    path = Path(db_path)
    if str(db_path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    run_migrations(conn)
    return conn
