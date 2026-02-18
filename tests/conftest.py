"""Shared pytest fixtures."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Generator
import sqlite3

import pytest

from stockwatch.providers.base import DataProvider, OHLCVRow
from stockwatch.storage.db import init_db

_FIXTURE_CSV = Path(__file__).parent / "fixtures" / "sample_ohlcv.csv"


def _load_fixture(ticker: str = "TEST") -> list[OHLCVRow]:
    rows: list[OHLCVRow] = []
    with open(_FIXTURE_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                OHLCVRow(
                    ticker=ticker,
                    date=date.fromisoformat(row["date"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    adj_close=float(row["adj_close"]),
                    volume=int(row["volume"]),
                    source="fixture",
                )
            )
    return rows


class MockDataProvider(DataProvider):
    """Returns fixture data for any ticker, optionally simulating errors."""

    def __init__(self, error_tickers: set[str] | None = None) -> None:
        self._error_tickers = error_tickers or set()

    @property
    def name(self) -> str:
        return "mock"

    def fetch_ohlcv(self, ticker: str, start: date, end: date) -> list[OHLCVRow]:
        from stockwatch.providers.base import ProviderError
        if ticker in self._error_tickers:
            raise ProviderError(f"Simulated error for {ticker}")
        rows = _load_fixture(ticker)
        return [r for r in rows if start <= r.date <= end]


@pytest.fixture()
def mock_provider() -> MockDataProvider:
    return MockDataProvider()


@pytest.fixture()
def mem_db() -> Generator[sqlite3.Connection, None, None]:
    """In-memory SQLite DB with schema applied."""
    conn = init_db(":memory:")
    yield conn
    conn.close()


@pytest.fixture()
def fixture_prices() -> list[float]:
    """60 adj_close values from the fixture CSV."""
    rows = _load_fixture()
    return [r.adj_close for r in rows]


@pytest.fixture()
def fixture_volumes() -> list[int]:
    """60 volume values from the fixture CSV."""
    rows = _load_fixture()
    return [r.volume for r in rows]
