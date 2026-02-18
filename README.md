# StockWatch

A daily stock trend monitor that fetches OHLCV data, computes technical indicators, classifies trend direction, and distributes results via CLI, file artifacts, email digest (Amazon SES), and optional X (Twitter) post.

**Target hosting:** single $4–6/mo VPS running Docker Compose with a systemd timer.

---

## Features

- Fetches historical and incremental OHLCV data from Yahoo Finance (free, no API key)
- Computes MA20/50, RSI-14, 1/5/20-day returns, annualised volatility, volume anomalies
- Classifies each ticker as **Uptrend / Downtrend / Sideways** via a weighted composite score (0–100)
- Ranks top gainers/losers and strongest trends into a daily digest
- Delivers via:
  - CLI pretty-print
  - JSON + Markdown file artifacts
  - HTML + plain-text email via Amazon SES
  - Tweet via X (Twitter) API v2
- Holiday guard — skips NYSE-closed days automatically
- Dry-run mode for testing without sending
- Structured JSON logging (`structlog`)
- HTTP healthcheck endpoint on `:8080`

---

## Architecture

```
systemd timer (4:30 PM ET, Mon–Fri)
       │
       ▼
  Orchestrator  ←  holiday guard
       │
  ┌────┴────┐
  │         │
DataFetcher  SQLite (WAL)
(yfinance)  prices | indicators | reports | email_logs | tweet_logs
       │
  Indicator Engine  →  Trend Classifier (score 0–100)
                              │
                        Digest Builder (Jinja2)
                        ┌──────┬──────────┬──────────┐
                        ▼      ▼          ▼          ▼
                       CLI  File(JSON   Email      X Post
                            +MD)       (SES)      (tweepy)
```

---

## Trend Scoring

| Component | Weight | Notes |
|---|---|---|
| MA Alignment | 30% | price vs MA20 vs MA50 |
| RSI-14 | 25% | Wilder EMA, 0–100 direct |
| 20-day Momentum | 30% | `50 + return_20d × 350`, clamped |
| Volatility Regime | 15% | Lower vol → higher score |

```
score ≥ 62  → Uptrend
score ≤ 38  → Downtrend
else        → Sideways
```

---

## Quick Start

**Requirements:** Python 3.12+, `uv` (or `pip`)

```bash
git clone https://github.com/makfasaee/stock-trend-monitor.git
cd stock-trend-monitor

# Create virtualenv and install
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your AWS / Twitter / OpenAI credentials

# Initialize database
python -m stockwatch migrate

# Backfill 252 days of history
python -m stockwatch backfill

# Run once
python -m stockwatch run
```

---

## CLI Commands

```bash
python -m stockwatch migrate    # Initialize / migrate the database
python -m stockwatch backfill   # Backfill historical prices for all tickers
python -m stockwatch run        # Run the pipeline once (today)
python -m stockwatch run --date 2024-03-27  # Run for a specific date
python -m stockwatch status     # Show last report and DB stats
python -m stockwatch scheduler  # Start the APScheduler daemon
```

---

## Configuration

Edit `config/settings.toml` to customise the watchlist, thresholds, and scheduling:

```toml
[watchlist]
tickers = ["AAPL", "MSFT", "GOOGL", ...]

[thresholds]
uptrend_min = 62.0
downtrend_max = 38.0
volume_anomaly_multiplier = 2.0

[scheduling]
run_hour = 16
run_minute = 30
run_timezone = "America/New_York"
```

Environment variables (`.env`):

| Variable | Purpose |
|---|---|
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | SES credentials |
| `SES_FROM_ADDRESS` | Verified sender address |
| `SES_RECIPIENT_ADDRESSES` | Comma-separated recipients |
| `TWITTER_*` | X API credentials |
| `OPENAI_API_KEY` | Optional LLM narrative |
| `ENABLE_EMAIL` | `true`/`false` (default `true`) |
| `ENABLE_TWITTER` | `true`/`false` (default `false`) |
| `DRY_RUN` | `true`/`false` — log but don't send |
| `DB_PATH` | SQLite file path |

---

## Docker

```bash
# Build
docker compose build

# One-off run
docker compose run --rm app python -m stockwatch run

# Start scheduler daemon
docker compose up -d
```

Data, logs, and reports are persisted in Docker volumes mounted at `./data`, `./logs`, `./reports`.

---

## Deployment (Hetzner CX22, ~$4–5/mo)

1. Provision Ubuntu 24.04 VPS, install Docker + Docker Compose
2. Clone repo to `/opt/stockwatch`; fill in `.env`
3. `docker compose build`
4. `docker compose run --rm app python -m stockwatch migrate`
5. `docker compose run --rm app python -m stockwatch backfill`
6. Install and enable systemd units:
   ```bash
   cp deploy/systemd/stockwatch.* /etc/systemd/system/
   systemctl enable --now stockwatch.timer
   ```
7. Monitor: `GET http://<VPS_IP>:8080/health`

---

## Testing

```bash
# Unit tests only (~0.1s)
pytest tests/unit/ -v

# Full suite including integration
pytest tests/ -v

# With coverage
pytest --cov=stockwatch --cov-fail-under=80 tests/
```

69 tests: 54 unit (pure, no I/O) + 15 integration (moto SES mock, tweepy mock, in-memory SQLite).

---

## Project Structure

```
stockwatch/
├── providers/        # DataProvider ABC + yfinance implementation
├── storage/          # SQLite connection, migrations, repository (all SQL)
├── delivery/         # CLI output, file writer, SES email, X poster
├── templates/        # Jinja2: email HTML/text, Markdown digest, tweet
├── utils/            # structlog config, tenacity retries, healthcheck
├── indicators.py     # Pure indicator functions (MA, RSI, returns, vol)
├── trend.py          # Composite scoring and classification
├── digest.py         # Digest builder and template rendering
├── orchestrator.py   # Pipeline coordinator
├── scheduler.py      # APScheduler setup
└── __main__.py       # CLI entry point

config/settings.toml  # Watchlist, thresholds, scheduling
deploy/               # systemd units, nginx config
scripts/              # backup.sh (rclone → Backblaze B2), migrate.py
```

---

## Cost Estimate

| Item | Monthly |
|---|---|
| Hetzner CX22 VPS | ~$4.10 |
| Yahoo Finance data | $0 |
| Amazon SES (~150 sends) | ~$0.02 |
| Backblaze B2 backup | $0 (free tier) |
| X API (21 posts/mo) | $0 |
| **Total** | **~$4–5** |

---

## License

MIT
