"""Write digest artifacts to the filesystem (JSON + Markdown)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from stockwatch.digest import DigestData


def write_artifacts(d: DigestData, reports_dir: str | Path = "reports") -> tuple[str, str]:
    """Write JSON and Markdown files for *d*.

    Returns:
        (json_path, markdown_path) as strings.
    """
    base = Path(reports_dir)
    base.mkdir(parents=True, exist_ok=True)

    date_str = d.run_date.isoformat()
    json_path = base / f"{date_str}.json"
    md_path = base / f"{date_str}.md"

    json_path.write_text(d.to_json(), encoding="utf-8")
    md_path.write_text(d.render_markdown(), encoding="utf-8")

    return str(json_path), str(md_path)
