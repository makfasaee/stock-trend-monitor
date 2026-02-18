"""Pretty-print digest to stdout."""

from __future__ import annotations

from stockwatch.digest import DigestData


def print_digest(d: DigestData) -> None:
    """Print a human-readable digest to stdout."""
    sep = "=" * 60
    print(sep)
    print(f"  StockWatch Digest — {d.run_date}")
    print(sep)
    print(f"  Tickers : {d.total}")
    print(f"  Uptrend : {d.uptrend_count}  Downtrend: {d.downtrend_count}  Sideways: {d.sideways_count}")
    print(f"  Avg strength: {d.avg_strength}/100")
    print()

    def _pct(v: float | None) -> str:
        return f"{v * 100:+.2f}%" if v is not None else "—"

    if d.top_gainers:
        print("  TOP GAINERS (1-day)")
        for r in d.top_gainers:
            print(f"    {r['ticker']:<8}  {_pct(r.get('return_1d'))}  {r['trend']} ({r['trend_strength']})")
        print()

    if d.top_losers:
        print("  TOP LOSERS (1-day)")
        for r in d.top_losers:
            print(f"    {r['ticker']:<8}  {_pct(r.get('return_1d'))}  {r['trend']} ({r['trend_strength']})")
        print()

    if d.strongest_up:
        print("  STRONGEST UPTRENDS")
        for r in d.strongest_up:
            rsi = f"{r['rsi14']:.1f}" if r.get("rsi14") is not None else "—"
            print(f"    {r['ticker']:<8}  score={r['trend_strength']}  RSI={rsi}")
        print()

    if d.strongest_down:
        print("  STRONGEST DOWNTRENDS")
        for r in d.strongest_down:
            rsi = f"{r['rsi14']:.1f}" if r.get("rsi14") is not None else "—"
            print(f"    {r['ticker']:<8}  score={r['trend_strength']}  RSI={rsi}")
        print()

    if d.volume_anomalies:
        print("  VOLUME ANOMALIES")
        for r in d.volume_anomalies:
            print(f"    {r['ticker']:<8}  {r['trend']}  1d={_pct(r.get('return_1d'))}")
        print()

    print(sep)
