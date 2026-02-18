"""Minimal HTTP healthcheck server on :8080."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class _HealthHandler(BaseHTTPRequestHandler):
    db_path: str = "data/stockwatch.db"

    def log_message(self, format: str, *args: object) -> None:
        # Suppress access logs to avoid polluting structlog JSON output
        pass

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return

        payload: dict = {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            row = conn.execute("SELECT run_date FROM reports ORDER BY id DESC LIMIT 1").fetchone()
            payload["last_run_date"] = row[0] if row else None
            count = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
            payload["report_count"] = count
            size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
            payload["db_size_bytes"] = size
            conn.close()
        except Exception as exc:
            payload["status"] = "degraded"
            payload["error"] = str(exc)

        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_healthcheck_server(host: str = "0.0.0.0", port: int = 8080, db_path: str = "data/stockwatch.db") -> None:
    """Start the healthcheck HTTP server in a daemon thread."""
    _HealthHandler.db_path = db_path
    server = HTTPServer((host, port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
