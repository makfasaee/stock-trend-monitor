"""Post digest tweet via tweepy v4+ with OAuth 2.0."""

from __future__ import annotations

import json
import sqlite3
from datetime import date

import tweepy

from stockwatch.digest import DigestData
from stockwatch.storage import repository
from stockwatch.utils.logging import get_logger

log = get_logger(__name__)


def post_digest_tweet(
    d: DigestData,
    report_id: int,
    conn: sqlite3.Connection,
    api_key: str,
    api_secret: str,
    access_token: str,
    access_token_secret: str,
    bearer_token: str,
    max_chars: int = 280,
    dry_run: bool = False,
) -> None:
    """Post a tweet for the digest and log the result.

    Skips posting if a successful tweet already exists for this run_date
    (deduplication guard).
    """
    run_date = d.run_date

    # Dedup guard
    if repository.has_tweet_for_date(conn, run_date):
        log.info("tweet_skipped_duplicate", run_date=run_date.isoformat())
        return

    tweet_text = d.render_tweet(max_chars=max_chars)

    log_record: dict = {
        "report_id": report_id,
        "run_date": run_date.isoformat(),
        "payload_text": tweet_text,
        "response_json": None,
        "tweet_id": None,
        "status": "dry_run",
        "error_message": None,
        "attempt_number": 1,
    }

    if dry_run:
        log.info("tweet_dry_run", text=tweet_text)
        repository.insert_tweet_log(conn, log_record)
        return

    client = tweepy.Client(
        bearer_token=bearer_token,
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )

    try:
        response = client.create_tweet(text=tweet_text)
        tweet_id = str(response.data["id"])
        response_data = {"id": tweet_id, "text": response.data.get("text", "")}
        log.info("tweet_posted", tweet_id=tweet_id)
        log_record["tweet_id"] = tweet_id
        log_record["response_json"] = response_data
        log_record["status"] = "posted"
    except tweepy.TweepyException as exc:
        error_msg = str(exc)
        log.error("tweet_failed", error=error_msg)
        log_record["status"] = "failed"
        log_record["error_message"] = error_msg

    repository.insert_tweet_log(conn, log_record)
