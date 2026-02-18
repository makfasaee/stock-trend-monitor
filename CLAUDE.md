# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

```bash
# Install (Python 3.12 required — system default may be older)
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run unit tests only (fast, ~0.1s, no I/O)
pytest tests/unit/ -v

# Run a single test
pytest tests/unit/test_indicators.py::TestRSI::test_all_up_returns_100 -v

# Coverage (80% gate)
pytest --cov=stockwatch --cov-fail-under=80 tests/

# Run the pipeline once
python -m stockwatch run

# Run for a specific date
python -m stockwatch run --date 2024-03-27

# Initialize DB / check status
python -m stockwatch migrate
python -m stockwatch status
```

## Architecture

The pipeline is linear and coordinator-driven: `orchestrator.py` is the single entry point for all business logic. It is called by both the CLI (`__main__.py`) and the scheduler (`scheduler.py`).

**Data flow:**

```
DataProvider (ABC) → upsert_prices → get_adj_close_series
                                           ↓
                              indicators.py (pure functions)
                                           ↓
                                trend.py → upsert_indicator
                                           ↓
                              digest.py → DigestData.build()
                                           ↓
                    ┌──────────────────────┴──────────────────────┐
               file_writer          email_sender            x_poster
               (JSON + MD)          (boto3/SES)             (tweepy)
```

**Key design rules:**
- All SQL lives in `storage/repository.py` — no raw SQL elsewhere.
- `indicators.py` contains only pure functions (no I/O, no DB). They take `Sequence[float]` / `Sequence[int]` and return scalars or `None` when history is insufficient.
- `trend.py` calls indicator functions and produces a `TrendResult` dataclass. Scoring weights: MA alignment 30%, RSI 25%, 20d momentum 30%, volatility 15%.
- `digest.py` builds `DigestData` (call `.build()` after construction) and renders all 4 Jinja2 templates from `stockwatch/templates/`.
- `config.py` is a singleton (`get_config()` / `reset_config()`). Tests that touch config must call `reset_config()` in teardown or use a fresh `Config(path)` directly.
- Feature flags (`ENABLE_EMAIL`, `ENABLE_TWITTER`, `DRY_RUN`) are env-var booleans read in `config.py`.

**Storage:** SQLite WAL mode. Schema is applied via `storage/db.py:run_migrations()` (idempotent `CREATE IF NOT EXISTS`). All upserts use `ON CONFLICT … DO UPDATE`.

**Scheduling:** Two-layer — APScheduler `CronTrigger` fires the job; the job itself calls `_is_market_open()` (via `pandas_market_calendars`) as a holiday guard before doing any work.

**Provider abstraction:** `DataProvider` ABC in `providers/base.py`. The yfinance implementation is the only production one; `AlphaVantageProvider` is a stub. The mock for tests is `tests/conftest.py:MockDataProvider`, which replays `tests/fixtures/sample_ohlcv.csv`.

## Testing Notes

- Integration tests use `freeze_time` to pin dates. Use a known NYSE trading day (e.g. `2024-03-27`) for tests that expect the pipeline to run, and a holiday (e.g. `2024-12-25`) for the skip test.
- SES integration tests require `from moto import mock_aws` (moto v5+; `mock_ses` was removed).
- Fixtures in `test_email.py` and `test_x_poster.py` return a `_DBFixture` dataclass with `.conn` and `.report_id` — not the raw `sqlite3.Connection` — because `sqlite3.Connection` doesn't allow arbitrary attribute assignment.
