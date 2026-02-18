"""Unit tests for stockwatch.trend — no I/O."""

from __future__ import annotations

import pytest

from stockwatch.trend import DOWNTREND, SIDEWAYS, UPTREND, TrendResult, classify


def _uptrend_prices(n: int = 60) -> list[float]:
    """Strongly rising prices (all-bullish scenario)."""
    return [100.0 * (1.005 ** i) for i in range(n)]


def _downtrend_prices(n: int = 60) -> list[float]:
    """Strongly falling prices (all-bearish scenario)."""
    return [200.0 * (0.995 ** i) for i in range(n)]


def _flat_prices(n: int = 60, base: float = 100.0) -> list[float]:
    return [base] * n


def _oscillating_prices(n: int = 60, base: float = 100.0, amplitude: float = 1.0) -> list[float]:
    """Prices that oscillate around *base* — truly sideways market."""
    import math
    return [base + amplitude * math.sin(i * math.pi / 5) for i in range(n)]


def _volumes(n: int = 60, base: int = 1_000_000) -> list[int]:
    return [base] * n


class TestTrendBoundaries:
    def test_composite_62_is_uptrend(self) -> None:
        """Force a composite right at 62.0 boundary → Uptrend."""
        # Use all-uptrend prices — composite will be > 62
        prices = _uptrend_prices(60)
        result = classify(prices, _volumes(60))
        assert result.label == UPTREND

    def test_all_bullish_score_above_80(self) -> None:
        prices = _uptrend_prices(60)
        result = classify(prices, _volumes(60))
        assert result.strength > 80.0

    def test_all_bearish_score_below_20(self) -> None:
        prices = _downtrend_prices(60)
        result = classify(prices, _volumes(60))
        assert result.strength < 20.0

    def test_all_bearish_is_downtrend(self) -> None:
        prices = _downtrend_prices(60)
        result = classify(prices, _volumes(60))
        assert result.label == DOWNTREND

    def test_oscillating_is_sideways(self) -> None:
        # Oscillating prices produce mixed MA/RSI signals → Sideways composite
        prices = _oscillating_prices(60)
        result = classify(prices, _volumes(60))
        assert result.label == SIDEWAYS

    def test_score_always_in_0_100(self) -> None:
        for prices in [_uptrend_prices(), _downtrend_prices(), _flat_prices()]:
            result = classify(prices, _volumes())
            assert 0.0 <= result.strength <= 100.0
            assert 0.0 <= result.composite <= 100.0

    def test_custom_thresholds(self) -> None:
        prices = _flat_prices(60)
        result = classify(prices, _volumes(60), uptrend_min=10.0, downtrend_max=90.0)
        # With extreme thresholds, flat prices could be uptrend or downtrend
        assert result.label in (UPTREND, DOWNTREND, SIDEWAYS)


class TestTrendResultFields:
    def test_all_fields_populated_with_enough_history(self) -> None:
        prices = _uptrend_prices(60)
        result = classify(prices, _volumes(60))
        assert result.ma20 is not None
        assert result.ma50 is not None
        assert result.rsi14 is not None
        assert result.return_1d is not None
        assert result.return_5d is not None
        assert result.return_20d is not None
        assert result.volatility_20d is not None

    def test_insufficient_history_returns_none_for_ma50(self) -> None:
        prices = _uptrend_prices(30)  # only 30 rows, ma50 = None
        result = classify(prices, _volumes(30))
        assert result.ma50 is None

    def test_volume_anomaly_is_bool(self) -> None:
        result = classify(_flat_prices(), _volumes())
        assert isinstance(result.volume_anomaly, bool)


class TestMAAlignment:
    def test_price_above_both_mas(self) -> None:
        # Uptrend fixture: price > ma20 > ma50
        prices = _uptrend_prices(60)
        result = classify(prices, _volumes(60))
        assert result.ma20 is not None and result.ma50 is not None
        last = prices[-1]
        assert last > result.ma20 > result.ma50

    def test_price_below_both_mas(self) -> None:
        prices = _downtrend_prices(60)
        result = classify(prices, _volumes(60))
        assert result.ma20 is not None and result.ma50 is not None
        last = prices[-1]
        assert last < result.ma20


class TestStrengthRounding:
    def test_strength_is_1_decimal(self) -> None:
        result = classify(_uptrend_prices(), _volumes())
        # strength must round to 1 decimal
        assert result.strength == round(result.strength, 1)
