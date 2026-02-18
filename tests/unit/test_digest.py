"""Unit tests for stockwatch.digest — no I/O."""

from __future__ import annotations

from datetime import date

import pytest

from stockwatch.digest import DigestData


def _make_indicator(
    ticker: str,
    trend: str = "Uptrend",
    strength: float = 70.0,
    return_1d: float | None = 0.01,
    volume_anomaly: bool = False,
) -> dict:
    return {
        "ticker": ticker,
        "date": "2024-03-27",
        "trend": trend,
        "trend_strength": strength,
        "return_1d": return_1d,
        "return_5d": None,
        "return_20d": 0.05,
        "rsi14": 65.0,
        "ma20": 220.0,
        "ma50": 210.0,
        "volatility_20d": 0.18,
        "volume_anomaly": int(volume_anomaly),
    }


def _build_digest(rows: list[dict]) -> DigestData:
    d = DigestData(run_date=date(2024, 3, 27), indicators=rows)
    d.build(top_n=5)
    return d


class TestDigestBuild:
    def test_counts_by_trend(self) -> None:
        rows = [
            _make_indicator("A", "Uptrend"),
            _make_indicator("B", "Uptrend"),
            _make_indicator("C", "Downtrend"),
            _make_indicator("D", "Sideways"),
        ]
        d = _build_digest(rows)
        assert d.uptrend_count == 2
        assert d.downtrend_count == 1
        assert d.sideways_count == 1
        assert d.total == 4

    def test_top_gainers_sorted_correctly(self) -> None:
        rows = [
            _make_indicator("A", return_1d=0.05),
            _make_indicator("B", return_1d=0.02),
            _make_indicator("C", return_1d=0.10),
        ]
        d = _build_digest(rows)
        tickers = [r["ticker"] for r in d.top_gainers]
        assert tickers[0] == "C"
        assert tickers[1] == "A"

    def test_top_losers_sorted_correctly(self) -> None:
        rows = [
            _make_indicator("A", return_1d=-0.01),
            _make_indicator("B", return_1d=-0.05),
            _make_indicator("C", return_1d=-0.03),
        ]
        d = _build_digest(rows)
        tickers = [r["ticker"] for r in d.top_losers]
        assert tickers[0] == "B"

    def test_volume_anomalies_filtered(self) -> None:
        rows = [
            _make_indicator("A", volume_anomaly=True),
            _make_indicator("B", volume_anomaly=False),
            _make_indicator("C", volume_anomaly=True),
        ]
        d = _build_digest(rows)
        anom_tickers = {r["ticker"] for r in d.volume_anomalies}
        assert "A" in anom_tickers
        assert "C" in anom_tickers
        assert "B" not in anom_tickers

    def test_empty_watchlist_handled(self) -> None:
        d = _build_digest([])
        assert d.total == 0
        assert d.top_gainers == []
        assert d.top_losers == []
        assert d.strongest_up == []

    def test_single_ticker(self) -> None:
        d = _build_digest([_make_indicator("AAPL")])
        assert d.total == 1
        assert len(d.top_gainers) == 1

    def test_avg_strength(self) -> None:
        rows = [
            _make_indicator("A", strength=60.0),
            _make_indicator("B", strength=80.0),
        ]
        d = _build_digest(rows)
        assert d.avg_strength == pytest.approx(70.0)


class TestDigestRendering:
    def _digest(self) -> DigestData:
        rows = [
            _make_indicator("AAPL", "Uptrend", 75.0, 0.02),
            _make_indicator("MSFT", "Downtrend", 30.0, -0.03),
            _make_indicator("GOOGL", "Sideways", 50.0, 0.005),
        ]
        return _build_digest(rows)

    def test_email_html_has_html_tag(self) -> None:
        html = self._digest().render_email_html()
        assert "<html" in html.lower()

    def test_email_text_no_exceptions(self) -> None:
        text = self._digest().render_email_text()
        assert "StockWatch" in text

    def test_markdown_has_table_headers(self) -> None:
        md = self._digest().render_markdown()
        assert "# StockWatch Digest" in md
        assert "|" in md

    def test_tweet_within_280_chars(self) -> None:
        tweet = self._digest().render_tweet(max_chars=280)
        assert len(tweet) <= 280

    def test_tweet_always_within_limit_for_any_valid_input(self) -> None:
        # Edge case: single ticker with extreme values
        rows = [_make_indicator("X" * 5, return_1d=99.9)]
        d = _build_digest(rows)
        tweet = d.render_tweet(max_chars=280)
        assert len(tweet) <= 280

    def test_to_json_is_valid_json(self) -> None:
        import json
        payload = json.loads(self._digest().to_json())
        assert "run_date" in payload
        assert "summary" in payload
        assert "top_movers" in payload
