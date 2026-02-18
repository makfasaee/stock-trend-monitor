#!/usr/bin/env bash
# Nightly backup of SQLite database to Backblaze B2
# Triggered by a separate systemd timer at 23:00 ET

set -euo pipefail

DB_PATH="${DB_PATH:-/app/data/stockwatch.db}"
BUCKET="${BACKBLAZE_BUCKET:-}"

if [ -z "$BUCKET" ]; then
    echo "ERROR: BACKBLAZE_BUCKET is not set" >&2
    exit 1
fi

if [ ! -f "$DB_PATH" ]; then
    echo "ERROR: Database not found at $DB_PATH" >&2
    exit 1
fi

echo "Backing up $DB_PATH to b2:$BUCKET ..."
rclone sync "$DB_PATH" "b2:${BUCKET}/backups/stockwatch.db" \
    --b2-account "${BACKBLAZE_KEY_ID}" \
    --b2-key "${BACKBLAZE_APPLICATION_KEY}"

echo "Backup complete."
