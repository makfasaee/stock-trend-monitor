"""Unit tests for stockwatch.indicators — no I/O."""

from __future__ import annotations

import math

import pytest

from stockwatch.indicators import (
    moving_average,
    period_return,
    rsi,
    volatility,
    volume_anomaly,
)


# ── moving_average ────────────────────────────────────────────────────────────

class TestMovingAverage:
    def test_correct_value(self) -> None:
        prices = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert moving_average(prices, 5) == pytest.approx(3.0)

    def test_last_window_used(self) -> None:
        prices = [100.0, 200.0, 1.0, 2.0, 3.0]
        assert moving_average(prices, 3) == pytest.approx(2.0)

    def test_returns_none_when_too_short(self) -> None:
        assert moving_average([1.0, 2.0], 3) is None

    def test_exact_length(self) -> None:
        prices = [10.0, 20.0, 30.0]
        assert moving_average(prices, 3) == pytest.approx(20.0)

    def test_nan_in_series_returns_none(self) -> None:
        assert moving_average([1.0, float("nan"), 3.0], 3) is None


# ── rsi ───────────────────────────────────────────────────────────────────────

class TestRSI:
    def _all_up(self, n: int = 30) -> list[float]:
        return [float(i) for i in range(1, n + 1)]

    def _all_down(self, n: int = 30) -> list[float]:
        return [float(n - i) for i in range(n)]

    def _alternating(self, n: int = 30) -> list[float]:
        # alternates +1 / -1 changes
        prices = [100.0]
        for i in range(1, n):
            prices.append(prices[-1] + (1.0 if i % 2 == 0 else -1.0))
        return prices

    def test_all_up_returns_100(self) -> None:
        result = rsi(self._all_up(), period=14)
        assert result == pytest.approx(100.0)

    def test_all_down_near_zero(self) -> None:
        result = rsi(self._all_down(), period=14)
        assert result is not None
        assert result < 5.0

    def test_alternating_near_50(self) -> None:
        result = rsi(self._alternating(60), period=14)
        assert result is not None
        assert 30.0 < result < 70.0

    def test_returns_none_insufficient_history(self) -> None:
        assert rsi([1.0, 2.0, 3.0], period=14) is None

    def test_returns_none_for_empty(self) -> None:
        assert rsi([], period=14) is None

    def test_div_by_zero_guard(self) -> None:
        # Series with zero losses → 100
        prices = list(range(1, 20))
        result = rsi(prices, period=14)
        assert result == pytest.approx(100.0)

    def test_result_in_0_100(self, fixture_prices: list[float]) -> None:
        result = rsi(fixture_prices, period=14)
        assert result is not None
        assert 0.0 <= result <= 100.0


# ── period_return ─────────────────────────────────────────────────────────────

class TestPeriodReturn:
    def test_positive_return(self) -> None:
        prices = [100.0, 110.0]
        assert period_return(prices, 1) == pytest.approx(0.10)

    def test_negative_return(self) -> None:
        prices = [100.0, 90.0]
        assert period_return(prices, 1) == pytest.approx(-0.10)

    def test_exactly_n_plus_1_rows(self) -> None:
        prices = [100.0, 105.0, 110.0]  # n=2 needs 3 rows
        assert period_return(prices, 2) == pytest.approx(0.10)

    def test_returns_none_when_too_short(self) -> None:
        assert period_return([100.0, 110.0], 5) is None

    def test_returns_none_for_zero_base(self) -> None:
        prices = [0.0, 100.0]
        assert period_return(prices, 1) is None

    def test_five_day_return(self) -> None:
        prices = [100.0, 101.0, 102.0, 103.0, 104.0, 110.0]
        assert period_return(prices, 5) == pytest.approx(0.10)


# ── volatility ────────────────────────────────────────────────────────────────

class TestVolatility:
    def test_flat_series_returns_zero(self) -> None:
        prices = [100.0] * 25
        result = volatility(prices, period=20)
        assert result == pytest.approx(0.0)

    def test_returns_none_insufficient(self) -> None:
        assert volatility([100.0] * 20, period=20) is None  # needs period + 1

    def test_result_non_negative(self, fixture_prices: list[float]) -> None:
        result = volatility(fixture_prices, period=20)
        assert result is not None
        assert result >= 0.0

    def test_known_value_constant_growth_is_zero_vol(self) -> None:
        # A perfectly geometric series has constant daily returns → zero variance → vol=0
        prices = [100.0 * (1.01 ** i) for i in range(25)]
        result = volatility(prices, period=20)
        assert result == pytest.approx(0.0)

    def test_variable_returns_produce_nonzero_vol(self) -> None:
        # Alternating +2%/-1% returns → non-zero variance
        prices = [100.0]
        for i in range(24):
            factor = 1.02 if i % 2 == 0 else 0.99
            prices.append(prices[-1] * factor)
        result = volatility(prices, period=20)
        assert result is not None
        assert result > 0.0


# ── volume_anomaly ────────────────────────────────────────────────────────────

class TestVolumeAnomaly:
    def _make_vols(self, base: int, last: int, n: int = 25) -> list[int]:
        return [base] * (n - 1) + [last]

    def test_exactly_2x_is_true(self) -> None:
        vols = self._make_vols(1_000_000, 2_000_000)
        assert volume_anomaly(vols) is True

    def test_below_2x_is_false(self) -> None:
        vols = self._make_vols(1_000_000, 1_999_999)
        assert volume_anomaly(vols) is False

    def test_returns_false_insufficient_history(self) -> None:
        assert volume_anomaly([1_000_000] * 10) is False

    def test_zero_volume_series_is_false(self) -> None:
        vols = [0] * 25
        assert volume_anomaly(vols) is False

    def test_fixture_volumes(self, fixture_volumes: list[int]) -> None:
        result = volume_anomaly(fixture_volumes)
        assert isinstance(result, bool)
