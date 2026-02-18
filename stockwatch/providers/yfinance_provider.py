"""yfinance-backed DataProvider implementation."""

from __future__ import annotations

import datetime
from datetime import date

import pandas as pd
import yfinance as yf

from stockwatch.providers.base import DataProvider, OHLCVRow, ProviderError


class YFinanceProvider(DataProvider):
    """Fetch OHLCV data from Yahoo Finance via yfinance (no API key required)."""

    @property
    def name(self) -> str:
        return "yfinance"

    def fetch_ohlcv(self, ticker: str, start: date, end: date) -> list[OHLCVRow]:
        """Download OHLCV from Yahoo Finance and return normalised rows.

        yfinance's *end* date is exclusive, so we add one day internally.
        """
        try:
            yf_end = end + datetime.timedelta(days=1)
            raw: pd.DataFrame = yf.download(
                ticker,
                start=start.isoformat(),
                end=yf_end.isoformat(),
                auto_adjust=False,
                progress=False,
                threads=False,
            )
        except Exception as exc:
            raise ProviderError(f"yfinance download failed for {ticker}: {exc}") from exc

        if raw.empty:
            return []

        # Flatten multi-level columns produced by yfinance >= 0.2.x when
        # downloading a single ticker.
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        rows: list[OHLCVRow] = []
        for idx, row in raw.iterrows():
            row_date = idx.date() if hasattr(idx, "date") else idx
            rows.append(
                OHLCVRow(
                    ticker=ticker,
                    date=row_date,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    adj_close=float(row["Adj Close"]),
                    volume=int(row["Volume"]),
                    source=self.name,
                )
            )

        return sorted(rows, key=lambda r: r.date)
