"""Trend classification and composite scoring (0–100)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from stockwatch.indicators import (
    moving_average,
    period_return,
    rsi,
    volatility,
    volume_anomaly as compute_volume_anomaly,
)

UPTREND = "Uptrend"
DOWNTREND = "Downtrend"
SIDEWAYS = "Sideways"

_UPTREND_MIN = 62.0
_DOWNTREND_MAX = 38.0


@dataclass
class TrendResult:
    label: str          # Uptrend | Downtrend | Sideways
    strength: float     # 0.0–100.0
    ma20: float | None
    ma50: float | None
    rsi14: float | None
    return_1d: float | None
    return_5d: float | None
    return_20d: float | None
    volatility_20d: float | None
    volume_anomaly: bool
    composite: float    # raw composite before label assignment


def _ma_score(price: float, ma20: float | None, ma50: float | None) -> float:
    """Score MA alignment on 0–100 scale."""
    if ma20 is None and ma50 is None:
        return 50.0
    if ma20 is None or ma50 is None:
        # Only one MA available
        ma = ma20 if ma20 is not None else ma50
        return 70.0 if price > ma else 30.0  # type: ignore[operator]
    # Both MAs available
    if price > ma20 and ma20 > ma50:
        return 90.0
    if price < ma20 and ma20 < ma50:
        return 10.0
    if price > ma20 and ma20 <= ma50:
        return 60.0
    if price < ma20 and ma20 >= ma50:
        return 40.0
    return 50.0


def _momentum_score(return_20d: float | None) -> float:
    """Map 20-day return to 0–100 scale."""
    if return_20d is None:
        return 50.0
    raw = 50.0 + return_20d * 350.0
    return max(0.0, min(100.0, raw))


def _volatility_score(vol: float | None) -> float:
    """Map annualised volatility to 0–100 scale (lower vol → higher score)."""
    if vol is None:
        return 50.0
    if vol < 0.15:
        return 70.0
    if vol < 0.25:
        return 55.0
    if vol < 0.40:
        return 40.0
    return 25.0


def classify(
    prices: Sequence[float],
    volumes: Sequence[int],
    uptrend_min: float = _UPTREND_MIN,
    downtrend_max: float = _DOWNTREND_MAX,
    volume_anomaly_multiplier: float = 2.0,
) -> TrendResult:
    """Compute the composite trend score and classify the ticker.

    Args:
        prices:  Adj-close series, oldest first (min ~50 values for full scoring).
        volumes: Volume series, same length as *prices*.

    Returns:
        TrendResult with label, strength, and all intermediate indicators.
    """
    price = prices[-1] if prices else 0.0

    ma20 = moving_average(prices, 20)
    ma50 = moving_average(prices, 50)
    rsi14 = rsi(prices, 14)
    ret_1d = period_return(prices, 1)
    ret_5d = period_return(prices, 5)
    ret_20d = period_return(prices, 20)
    vol_20d = volatility(prices, 20)
    vol_anom = compute_volume_anomaly(volumes, multiplier=volume_anomaly_multiplier)

    ma_s = _ma_score(price, ma20, ma50)
    rsi_s = rsi14 if rsi14 is not None else 50.0
    mom_s = _momentum_score(ret_20d)
    vol_s = _volatility_score(vol_20d)

    composite = 0.30 * ma_s + 0.25 * rsi_s + 0.30 * mom_s + 0.15 * vol_s
    composite = max(0.0, min(100.0, composite))

    if composite >= uptrend_min:
        label = UPTREND
    elif composite <= downtrend_max:
        label = DOWNTREND
    else:
        label = SIDEWAYS

    return TrendResult(
        label=label,
        strength=round(composite, 1),
        ma20=ma20,
        ma50=ma50,
        rsi14=rsi14,
        return_1d=ret_1d,
        return_5d=ret_5d,
        return_20d=ret_20d,
        volatility_20d=vol_20d,
        volume_anomaly=vol_anom,
        composite=composite,
    )
