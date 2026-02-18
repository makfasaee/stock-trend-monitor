"""Send HTML+text multipart digest email via Amazon SES."""

from __future__ import annotations

import json
import sqlite3
from datetime import date

import boto3
from botocore.exceptions import ClientError

from stockwatch.digest import DigestData
from stockwatch.storage import repository
from stockwatch.utils.logging import get_logger

log = get_logger(__name__)


def send_digest_email(
    d: DigestData,
    report_id: int,
    conn: sqlite3.Connection,
    from_address: str,
    recipient_addresses: list[str],
    aws_region: str = "us-east-1",
    dry_run: bool = False,
) -> None:
    """Send the digest email and log the result.

    Args:
        d:                   DigestData (already built).
        report_id:           FK into reports table.
        conn:                Open SQLite connection for logging.
        from_address:        Verified SES sender address.
        recipient_addresses: List of recipient emails.
        aws_region:          AWS region for SES endpoint.
        dry_run:             If True, log but do not actually send.
    """
    subject = f"StockWatch Digest — {d.run_date}"
    html_body = d.render_email_html()
    text_body = d.render_email_text()

    log_record: dict = {
        "report_id": report_id,
        "recipients_json": recipient_addresses,
        "subject": subject,
        "ses_message_id": None,
        "status": "dry_run",
        "error_message": None,
        "attempt_number": 1,
    }

    if dry_run:
        log.info("email_dry_run", subject=subject, recipients=recipient_addresses)
        repository.insert_email_log(conn, log_record)
        return

    client = boto3.client("ses", region_name=aws_region)
    try:
        response = client.send_email(
            Source=from_address,
            Destination={"ToAddresses": recipient_addresses},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                },
            },
        )
        message_id = response["MessageId"]
        log.info("email_sent", message_id=message_id, recipients=recipient_addresses)
        log_record["ses_message_id"] = message_id
        log_record["status"] = "sent"
    except ClientError as exc:
        error_msg = str(exc)
        log.error("email_failed", error=error_msg)
        log_record["status"] = "failed"
        log_record["error_message"] = error_msg

    repository.insert_email_log(conn, log_record)
