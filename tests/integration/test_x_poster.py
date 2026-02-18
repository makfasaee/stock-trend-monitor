"""Integration tests for x_poster — unittest.mock on tweepy.Client."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
import tweepy

from stockwatch.delivery.x_poster import post_digest_tweet
from stockwatch.digest import DigestData
from stockwatch.storage.db import init_db
from stockwatch.storage import repository


class _DBFixture:
    def __init__(self, conn, report_id: int) -> None:
        self.conn = conn
        self.report_id = report_id


_RUN_DATE = date(2024, 3, 27)

_TWITTER_CREDS = dict(
    api_key="key",
    api_secret="secret",
    access_token="tok",
    access_token_secret="tok_secret",
    bearer_token="bearer",
)


def _make_digest() -> DigestData:
    rows = [
        {
            "ticker": "AAPL",
            "date": "2024-03-27",
            "trend": "Uptrend",
            "trend_strength": 72.0,
            "return_1d": 0.02,
            "return_5d": 0.05,
            "return_20d": 0.10,
            "rsi14": 65.0,
            "ma20": 220.0,
            "ma50": 210.0,
            "volatility_20d": 0.18,
            "volume_anomaly": 0,
        }
    ]
    d = DigestData(run_date=_RUN_DATE, indicators=rows)
    d.build()
    return d


_REPORT_RECORD = {
    "run_date": _RUN_DATE.isoformat(),
    "ticker_count": 1,
    "uptrend_count": 1,
    "downtrend_count": 0,
    "sideways_count": 0,
    "top_movers_json": "{}",
    "summary_text": None,
    "summary_html": None,
    "markdown_path": None,
    "json_path": None,
    "llm_used": 0,
}


@pytest.fixture()
def db():
    conn = init_db(":memory:")
    report_id = repository.insert_report(conn, _REPORT_RECORD)
    yield _DBFixture(conn, report_id)
    conn.close()


def test_valid_digest_posts_tweet_and_logs(db) -> None:
    mock_client = MagicMock()
    mock_client.create_tweet.return_value = MagicMock(data={"id": "12345", "text": "hi"})

    with patch("stockwatch.delivery.x_poster.tweepy.Client", return_value=mock_client):
        post_digest_tweet(
            d=_make_digest(),
            report_id=db.report_id,
            conn=db.conn,
            **_TWITTER_CREDS,
            dry_run=False,
        )

    mock_client.create_tweet.assert_called_once()
    log = db.conn.execute("SELECT * FROM tweet_logs ORDER BY id DESC LIMIT 1").fetchone()
    assert log["status"] == "posted"
    assert log["tweet_id"] == "12345"


def test_tweet_id_captured_in_log(db) -> None:
    mock_client = MagicMock()
    mock_client.create_tweet.return_value = MagicMock(data={"id": "99999", "text": "test"})

    with patch("stockwatch.delivery.x_poster.tweepy.Client", return_value=mock_client):
        post_digest_tweet(
            d=_make_digest(),
            report_id=db.report_id,
            conn=db.conn,
            **_TWITTER_CREDS,
            dry_run=False,
        )

    log = db.conn.execute("SELECT tweet_id FROM tweet_logs ORDER BY id DESC LIMIT 1").fetchone()
    assert log["tweet_id"] == "99999"


def test_dry_run_does_not_call_create_tweet(db) -> None:
    mock_client = MagicMock()

    with patch("stockwatch.delivery.x_poster.tweepy.Client", return_value=mock_client):
        post_digest_tweet(
            d=_make_digest(),
            report_id=db.report_id,
            conn=db.conn,
            **_TWITTER_CREDS,
            dry_run=True,
        )

    mock_client.create_tweet.assert_not_called()
    log = db.conn.execute("SELECT * FROM tweet_logs ORDER BY id DESC LIMIT 1").fetchone()
    assert log["status"] == "dry_run"


def test_duplicate_guard_skips_posting(db) -> None:
    """If a posted tweet_log already exists for the run_date, skip posting."""
    repository.insert_tweet_log(
        db.conn,
        {
            "report_id": db.report_id,
            "run_date": _RUN_DATE.isoformat(),
            "payload_text": "existing tweet",
            "response_json": None,
            "tweet_id": "11111",
            "status": "posted",
            "error_message": None,
            "attempt_number": 1,
        },
    )

    mock_client = MagicMock()
    with patch("stockwatch.delivery.x_poster.tweepy.Client", return_value=mock_client):
        post_digest_tweet(
            d=_make_digest(),
            report_id=db.report_id,
            conn=db.conn,
            **_TWITTER_CREDS,
            dry_run=False,
        )

    mock_client.create_tweet.assert_not_called()


def test_tweepy_exception_logs_failed_no_crash(db) -> None:
    mock_client = MagicMock()
    mock_client.create_tweet.side_effect = tweepy.TweepyException("rate limit")

    with patch("stockwatch.delivery.x_poster.tweepy.Client", return_value=mock_client):
        post_digest_tweet(
            d=_make_digest(),
            report_id=db.report_id,
            conn=db.conn,
            **_TWITTER_CREDS,
            dry_run=False,
        )

    log = db.conn.execute("SELECT * FROM tweet_logs ORDER BY id DESC LIMIT 1").fetchone()
    assert log["status"] == "failed"
    assert "rate limit" in log["error_message"]


def test_response_json_stored(db) -> None:
    mock_client = MagicMock()
    mock_client.create_tweet.return_value = MagicMock(data={"id": "77777", "text": "hello"})

    with patch("stockwatch.delivery.x_poster.tweepy.Client", return_value=mock_client):
        post_digest_tweet(
            d=_make_digest(),
            report_id=db.report_id,
            conn=db.conn,
            **_TWITTER_CREDS,
            dry_run=False,
        )

    import json
    log = db.conn.execute("SELECT response_json FROM tweet_logs ORDER BY id DESC LIMIT 1").fetchone()
    payload = json.loads(log["response_json"])
    assert payload["id"] == "77777"
