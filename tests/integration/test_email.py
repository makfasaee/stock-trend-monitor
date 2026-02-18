"""Integration tests for email_sender — moto mock for SES."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from stockwatch.delivery.email_sender import send_digest_email
from stockwatch.digest import DigestData
from stockwatch.storage.db import init_db
from stockwatch.storage import repository


class _DBFixture:
    """Holds both the connection and the pre-inserted report_id."""
    def __init__(self, conn, report_id: int) -> None:
        self.conn = conn
        self.report_id = report_id


_FROM = "stockwatch@example.com"
_TO = ["user@example.com"]
_REGION = "us-east-1"
_RUN_DATE = date(2024, 3, 27)


def _make_digest() -> DigestData:
    rows = [
        {
            "ticker": "AAPL",
            "date": "2024-03-27",
            "trend": "Uptrend",
            "trend_strength": 72.0,
            "return_1d": 0.015,
            "return_5d": 0.04,
            "return_20d": 0.08,
            "rsi14": 62.0,
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


@mock_aws
def test_valid_digest_sends_email_and_logs(db) -> None:
    ses = boto3.client("ses", region_name=_REGION)
    ses.verify_email_identity(EmailAddress=_FROM)

    digest = _make_digest()
    send_digest_email(
        d=digest,
        report_id=db.report_id,
        conn=db.conn,
        from_address=_FROM,
        recipient_addresses=_TO,
        aws_region=_REGION,
        dry_run=False,
    )

    log = db.conn.execute("SELECT * FROM email_logs ORDER BY id DESC LIMIT 1").fetchone()
    assert log is not None
    assert log["status"] == "sent"
    assert log["ses_message_id"] is not None


@mock_aws
def test_ses_message_id_captured(db) -> None:
    ses = boto3.client("ses", region_name=_REGION)
    ses.verify_email_identity(EmailAddress=_FROM)

    digest = _make_digest()
    send_digest_email(
        d=digest,
        report_id=db.report_id,
        conn=db.conn,
        from_address=_FROM,
        recipient_addresses=_TO,
        aws_region=_REGION,
        dry_run=False,
    )

    log = db.conn.execute("SELECT ses_message_id FROM email_logs ORDER BY id DESC LIMIT 1").fetchone()
    assert log["ses_message_id"] is not None
    assert len(log["ses_message_id"]) > 0


@mock_aws
def test_dry_run_does_not_call_ses(db) -> None:
    digest = _make_digest()
    send_digest_email(
        d=digest,
        report_id=db.report_id,
        conn=db.conn,
        from_address=_FROM,
        recipient_addresses=_TO,
        aws_region=_REGION,
        dry_run=True,
    )

    log = db.conn.execute("SELECT * FROM email_logs ORDER BY id DESC LIMIT 1").fetchone()
    assert log["status"] == "dry_run"
    assert log["ses_message_id"] is None


@mock_aws
def test_ses_client_error_logs_failed(db) -> None:
    # Do NOT verify the sender — SES will raise MessageRejected
    digest = _make_digest()
    send_digest_email(
        d=digest,
        report_id=db.report_id,
        conn=db.conn,
        from_address=_FROM,
        recipient_addresses=_TO,
        aws_region=_REGION,
        dry_run=False,
    )

    log = db.conn.execute("SELECT * FROM email_logs ORDER BY id DESC LIMIT 1").fetchone()
    assert log["status"] == "failed"
    assert log["error_message"] is not None
