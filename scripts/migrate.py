#!/usr/bin/env python3
"""Run DB migrations — idempotent, safe to run multiple times."""

import sys
from pathlib import Path

# Allow running as a standalone script from the repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from stockwatch.config import get_config
from stockwatch.storage.db import init_db

if __name__ == "__main__":
    config = get_config()
    conn = init_db(config.db_path)
    conn.close()
    print(f"Migrations applied. Database ready at: {config.db_path}")
