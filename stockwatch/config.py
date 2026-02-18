"""Load configuration from TOML file and merge environment variables."""

from __future__ import annotations

import os
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.toml"


def _load_toml(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _env_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key, "").lower()
    if val in ("1", "true", "yes"):
        return True
    if val in ("0", "false", "no"):
        return False
    return default


class Config:
    """Application configuration.  Reads settings.toml then overlays env vars."""

    def __init__(self, config_path: Path | None = None) -> None:
        path = config_path or Path(os.environ.get("STOCKWATCH_CONFIG", str(_DEFAULT_CONFIG_PATH)))
        raw = _load_toml(path)

        # ── Watchlist ─────────────────────────────────────────────────────────
        self.tickers: list[str] = raw["watchlist"]["tickers"]

        # ── Thresholds ────────────────────────────────────────────────────────
        t = raw["thresholds"]
        self.uptrend_min: float = float(t["uptrend_min"])
        self.downtrend_max: float = float(t["downtrend_max"])
        self.volume_anomaly_multiplier: float = float(t["volume_anomaly_multiplier"])
        self.top_movers_count: int = int(t["top_movers_count"])

        # ── Indicators ────────────────────────────────────────────────────────
        ind = raw["indicators"]
        self.ma_short: int = int(ind["ma_short"])
        self.ma_long: int = int(ind["ma_long"])
        self.rsi_period: int = int(ind["rsi_period"])
        self.return_periods: list[int] = [int(x) for x in ind["return_periods"]]
        self.volatility_period: int = int(ind["volatility_period"])
        self.backfill_days: int = int(ind["backfill_days"])

        # ── Scheduling ────────────────────────────────────────────────────────
        sch = raw["scheduling"]
        self.run_hour: int = int(sch["run_hour"])
        self.run_minute: int = int(sch["run_minute"])
        self.run_timezone: str = sch["run_timezone"]
        self.market_calendar: str = sch["market_calendar"]
        self.misfire_grace_seconds: int = int(sch["misfire_grace_seconds"])

        # ── Digest ────────────────────────────────────────────────────────────
        dig = raw["digest"]
        self.max_tweet_chars: int = int(dig["max_tweet_chars"])

        # ── Healthcheck ───────────────────────────────────────────────────────
        hc = raw["healthcheck"]
        self.healthcheck_port: int = int(hc["port"])
        self.healthcheck_host: str = hc["host"]

        # ── Logging ───────────────────────────────────────────────────────────
        log = raw["logging"]
        self.log_level: str = os.environ.get("LOG_LEVEL", log["level"]).upper()

        # ── Env-var overlays ──────────────────────────────────────────────────
        self.db_path: str = os.environ.get("DB_PATH", "data/stockwatch.db")

        # AWS SES
        self.ses_from_address: str = os.environ.get("SES_FROM_ADDRESS", "")
        self.ses_recipient_addresses: list[str] = [
            addr.strip()
            for addr in os.environ.get("SES_RECIPIENT_ADDRESSES", "").split(",")
            if addr.strip()
        ]
        self.aws_region: str = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

        # X (Twitter)
        self.twitter_bearer_token: str = os.environ.get("TWITTER_BEARER_TOKEN", "")
        self.twitter_api_key: str = os.environ.get("TWITTER_API_KEY", "")
        self.twitter_api_secret: str = os.environ.get("TWITTER_API_SECRET", "")
        self.twitter_access_token: str = os.environ.get("TWITTER_ACCESS_TOKEN", "")
        self.twitter_access_token_secret: str = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")

        # OpenAI
        self.openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")

        # Feature flags
        self.enable_email: bool = _env_bool("ENABLE_EMAIL", True)
        self.enable_twitter: bool = _env_bool("ENABLE_TWITTER", False)
        self.enable_llm: bool = _env_bool("ENABLE_LLM", False)
        self.dry_run: bool = _env_bool("DRY_RUN", False)


_instance: Config | None = None


def get_config(config_path: Path | None = None) -> Config:
    """Return the singleton Config, creating it on first call."""
    global _instance
    if _instance is None:
        _instance = Config(config_path)
    return _instance


def reset_config() -> None:
    """Reset the singleton (useful in tests)."""
    global _instance
    _instance = None
