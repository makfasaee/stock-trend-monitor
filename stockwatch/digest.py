"""Digest builder — ranks tickers and renders Jinja2 templates."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


@dataclass
class DigestData:
    """All data needed to render every template."""

    run_date: date
    indicators: list[dict[str, Any]]   # raw rows from repository

    # Computed by build()
    total: int = 0
    uptrend_count: int = 0
    downtrend_count: int = 0
    sideways_count: int = 0
    avg_strength: float = 0.0
    top_gainers: list[dict[str, Any]] = field(default_factory=list)
    top_losers: list[dict[str, Any]] = field(default_factory=list)
    strongest_up: list[dict[str, Any]] = field(default_factory=list)
    strongest_down: list[dict[str, Any]] = field(default_factory=list)
    volume_anomalies: list[dict[str, Any]] = field(default_factory=list)

    def build(self, top_n: int = 5) -> "DigestData":
        """Compute all derived fields from the raw indicators list."""
        rows = self.indicators
        self.total = len(rows)

        up = [r for r in rows if r["trend"] == "Uptrend"]
        dn = [r for r in rows if r["trend"] == "Downtrend"]
        sw = [r for r in rows if r["trend"] == "Sideways"]

        self.uptrend_count = len(up)
        self.downtrend_count = len(dn)
        self.sideways_count = len(sw)

        if self.total:
            self.avg_strength = round(
                sum(r["trend_strength"] for r in rows) / self.total, 1
            )

        def _sortable(r: dict, key: str) -> float:
            v = r.get(key)
            return v if v is not None else 0.0

        self.top_gainers = sorted(
            [r for r in rows if r.get("return_1d") is not None],
            key=lambda r: r["return_1d"],
            reverse=True,
        )[:top_n]

        self.top_losers = sorted(
            [r for r in rows if r.get("return_1d") is not None],
            key=lambda r: r["return_1d"],
        )[:top_n]

        self.strongest_up = sorted(up, key=lambda r: r["trend_strength"], reverse=True)[:top_n]
        self.strongest_down = sorted(dn, key=lambda r: r["trend_strength"], reverse=True)[:top_n]
        self.volume_anomalies = [r for r in rows if r.get("volume_anomaly")]
        return self

    def top_movers_dict(self) -> dict[str, Any]:
        return {
            "top_gainers": self.top_gainers,
            "top_losers": self.top_losers,
            "strongest_up": self.strongest_up,
            "strongest_down": self.strongest_down,
            "volume_anomalies": self.volume_anomalies,
        }

    # ── Rendering ─────────────────────────────────────────────────────────────

    def render_email_html(self) -> str:
        env = _jinja_env()
        tmpl = env.get_template("email_html.j2")
        return tmpl.render(d=self)

    def render_email_text(self) -> str:
        env = _jinja_env()
        tmpl = env.get_template("email_text.j2")
        return tmpl.render(d=self)

    def render_markdown(self) -> str:
        env = _jinja_env()
        # Autoescape not needed for markdown
        md_env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        tmpl = md_env.get_template("digest_markdown.j2")
        return tmpl.render(d=self)

    def render_tweet(self, max_chars: int = 280) -> str:
        env = _jinja_env()
        md_env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        tmpl = md_env.get_template("tweet.j2")
        text = tmpl.render(d=self)
        # Hard truncate as a safety net (should not happen with well-crafted template)
        if len(text) > max_chars:
            text = text[: max_chars - 1] + "…"
        return text

    def to_json(self) -> str:
        return json.dumps(
            {
                "run_date": self.run_date.isoformat(),
                "summary": {
                    "total": self.total,
                    "uptrend_count": self.uptrend_count,
                    "downtrend_count": self.downtrend_count,
                    "sideways_count": self.sideways_count,
                    "avg_strength": self.avg_strength,
                },
                "top_movers": self.top_movers_dict(),
                "all_indicators": self.indicators,
            },
            indent=2,
            default=str,
        )
