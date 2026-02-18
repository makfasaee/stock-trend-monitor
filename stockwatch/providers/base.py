"""Abstract base class for OHLCV data providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class OHLCVRow:
    """Single row of OHLCV data for one ticker on one date."""

    ticker: str
    date: date
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: int
    source: str


class DataProvider(ABC):
    """Abstract interface for market-data sources.

    Concrete implementations must be drop-in replaceable so the rest of the
    pipeline never knows which provider is active.
    """

    @abstractmethod
    def fetch_ohlcv(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> list[OHLCVRow]:
        """Return OHLCV rows for *ticker* between *start* and *end* inclusive.

        Args:
            ticker: Ticker symbol (e.g. "AAPL").
            start:  First date to include (inclusive).
            end:    Last date to include (inclusive).

        Returns:
            List of OHLCVRow, sorted by date ascending.  May be empty if the
            ticker has no trading days in the requested range.

        Raises:
            ProviderError: If the data source returns an unrecoverable error.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g. "yfinance")."""


class ProviderError(Exception):
    """Raised when a data provider cannot fulfil a request."""
