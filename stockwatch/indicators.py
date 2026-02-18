"""Pure indicator functions — no I/O, no side effects.

All functions accept a list of (adj_close, volume) values (oldest first) and
return a scalar or None when there is insufficient history.
"""

from __future__ import annotations

import math
from typing import Sequence


def _validate(series: Sequence[float], min_len: int) -> bool:
    return len(series) >= min_len and not any(math.isnan(v) for v in series)


# ── Moving Averages ───────────────────────────────────────────────────────────

def moving_average(prices: Sequence[float], window: int) -> float | None:
    """Simple moving average of the last *window* values."""
    if not _validate(prices, window):
        return None
    tail = list(prices)[-window:]
    return sum(tail) / window


# ── RSI (Wilder's EMA method) ─────────────────────────────────────────────────

def rsi(prices: Sequence[float], period: int = 14) -> float | None:
    """Compute RSI using Wilder's smoothed moving average.

    Returns None when there are fewer than *period* + 1 data points.
    Returns 100.0 when average loss is zero (all-up series).
    """
    if not _validate(prices, period + 1):
        return None

    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

    # Seed with simple average of first *period* gains/losses
    gains = [max(d, 0.0) for d in deltas[:period]]
    losses = [abs(min(d, 0.0)) for d in deltas[:period]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    # Wilder smoothing over remaining deltas
    for delta in deltas[period:]:
        gain = max(delta, 0.0)
        loss = abs(min(delta, 0.0))
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - 100.0 / (1.0 + rs), 4)


# ── Returns ───────────────────────────────────────────────────────────────────

def period_return(prices: Sequence[float], n: int) -> float | None:
    """Return the n-day return: prices[-1]/prices[-(n+1)] - 1.

    Returns None when the series is too short.
    """
    if not _validate(prices, n + 1):
        return None
    p_now = prices[-1]
    p_prev = prices[-(n + 1)]
    if p_prev == 0.0:
        return None
    return p_now / p_prev - 1.0


# ── Volatility (annualised) ───────────────────────────────────────────────────

def volatility(prices: Sequence[float], period: int = 20) -> float | None:
    """Annualised volatility of daily % changes over the last *period* days.

    Returns None when there are fewer than *period* + 1 data points.
    Returns 0.0 for flat (zero-variance) series.
    """
    if not _validate(prices, period + 1):
        return None
    tail = list(prices)[-(period + 1):]
    daily_returns = [tail[i] / tail[i - 1] - 1.0 for i in range(1, len(tail))]
    n = len(daily_returns)
    mean = sum(daily_returns) / n
    variance = sum((r - mean) ** 2 for r in daily_returns) / n
    std_dev = math.sqrt(variance)
    return round(std_dev * math.sqrt(252), 6)


# ── Volume anomaly ────────────────────────────────────────────────────────────

def volume_anomaly(volumes: Sequence[int], multiplier: float = 2.0, window: int = 20) -> bool:
    """Return True if today's volume is >= *multiplier* × 20-day average.

    Returns False for insufficient history or zero-volume series.
    """
    if len(volumes) < window + 1:
        return False
    avg_vol = sum(volumes[-(window + 1):-1]) / window
    if avg_vol == 0:
        return False
    return volumes[-1] >= multiplier * avg_vol
