"""Alpha Vantage DataProvider stub — not implemented for MVP."""

from __future__ import annotations

from datetime import date

from stockwatch.providers.base import DataProvider, OHLCVRow, ProviderError


class AlphaVantageProvider(DataProvider):
    """Stub provider for Alpha Vantage.

    Replace the body of ``fetch_ohlcv`` with a real implementation when you
    want to swap away from yfinance (e.g. for higher rate limits or adjusted
    data guarantees).
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "alpha_vantage"

    def fetch_ohlcv(self, ticker: str, start: date, end: date) -> list[OHLCVRow]:
        raise ProviderError(
            "AlphaVantageProvider is not implemented. "
            "Switch to YFinanceProvider or implement this class."
        )
