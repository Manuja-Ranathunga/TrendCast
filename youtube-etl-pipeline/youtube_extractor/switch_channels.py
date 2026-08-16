"""
================================================================================
switch_channels.py — Archive Old Data & Seed New Channels
================================================================================
Usage:
    python youtube_extractor/switch_channels.py --csv youtube_extractor/enriched_channels_list.csv

    # Dry-run mode (prints SQL, does not execute):
    python youtube_extractor/switch_channels.py --csv youtube_extractor/enriched_channels_list.csv --dry-run

Environment Variables:
    SUPABASE_DB_URL   — PostgreSQL connection string (required)
================================================================================
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

import psycopg2
from psycopg2.extras import execute_batch

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL — Archive existing data
# ---------------------------------------------------------------------------
ARCHIVE_CHANNEL_STATS_SQL = """
INSERT INTO channel_stats_archive (
    channel_id, channel_title, channel_description, published_at,
    country, total_views, subscriber_count, video_count,
    processed_at, created_at, title, tier_category,
    uploads_playlist_id, last_checked_at
)
SELECT
    channel_id, channel_title, channel_description, published_at,
    country, total_views, subscriber_count, video_count,
    processed_at, created_at, title, tier_category,
    uploads_playlist_id, last_checked_at
FROM channel_stats;
"""

ARCHIVE_VIDEOS_SQL = """
INSERT INTO videos_archive (
    video_id, channel_id, published_at, status,
    last_polled_at, next_poll_at, current_interval_hours, created_at
)
SELECT
    video_id, channel_id, published_at, status,
    last_polled_at, next_poll_at, current_interval_hours, created_at
FROM videos;
"""

ARCHIVE_VIEW_TIMESERIES_SQL = """
INSERT INTO view_timeseries_archive (
    original_id, video_id, scraped_at,
    view_count, like_count, comment_count
)
SELECT
    id, video_id, scraped_at,
    view_count, like_count, comment_count
FROM view_timeseries;
"""

# ---------------------------------------------------------------------------
# SQL — Create archive tables (idempotent, mirrors 02_archive_and_switch_channels.sql)
# ---------------------------------------------------------------------------
CREATE_ARCHIVE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS channel_stats_archive (
    archive_id              BIGSERIAL       PRIMARY KEY,
    archived_at             TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    channel_id              VARCHAR(64)     NOT NULL,
    channel_title           VARCHAR(255)    NOT NULL,
    channel_description     TEXT,
    published_at            TIMESTAMPTZ,
    country                 VARCHAR(10),
    total_views             BIGINT          NOT NULL DEFAULT 0,
    subscriber_count        BIGINT          NOT NULL DEFAULT 0,
    video_count             INTEGER         NOT NULL DEFAULT 0,
    processed_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ,
    title                   VARCHAR(255),
    tier_category           VARCHAR(64),
    uploads_playlist_id     VARCHAR(64),
    last_checked_at         TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS videos_archive (
    archive_id              BIGSERIAL       PRIMARY KEY,
    archived_at             TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    video_id                VARCHAR(64)     NOT NULL,
    channel_id              VARCHAR(64)     NOT NULL,
    published_at            TIMESTAMPTZ     NOT NULL,
    status                  VARCHAR(16)     NOT NULL DEFAULT 'active',
    last_polled_at          TIMESTAMPTZ,
    next_poll_at            TIMESTAMPTZ,
    current_interval_hours  INTEGER         NOT NULL DEFAULT 6,
    created_at              TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS view_timeseries_archive (
    archive_id              BIGSERIAL       PRIMARY KEY,
    archived_at             TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    original_id             BIGINT,
    video_id                VARCHAR(64)     NOT NULL,
    scraped_at              TIMESTAMPTZ     NOT NULL,
    view_count              BIGINT          NOT NULL DEFAULT 0,
    like_count              BIGINT          NOT NULL DEFAULT 0,
    comment_count           BIGINT          NOT NULL DEFAULT 0
);
"""

# ---------------------------------------------------------------------------
# SQL — Clear active tables (order matters: FK cascade)
# ---------------------------------------------------------------------------
TRUNCATE_ACTIVE_SQL = [
    "DELETE FROM view_timeseries;",
    "DELETE FROM videos;",
    "DELETE FROM channel_stats;",
]

# ---------------------------------------------------------------------------
# SQL — Seed new channel
# ---------------------------------------------------------------------------
UPSERT_CHANNEL_SQL = """
INSERT INTO channel_stats (
    channel_id,
    channel_title,
    country,
    subscriber_count,
    total_views,
    uploads_playlist_id,
    title,
    processed_at
) VALUES (
    %(channel_id)s,
    %(channel_title)s,
    %(country)s,
    %(subscriber_count)s,
    %(total_views)s,
    %(uploads_playlist_id)s,
    %(channel_title)s,
    CURRENT_TIMESTAMP
)
ON CONFLICT (channel_id) DO UPDATE SET
    channel_title           = EXCLUDED.channel_title,
    country                 = EXCLUDED.country,
    subscriber_count        = EXCLUDED.subscriber_count,
    total_views             = EXCLUDED.total_views,
    uploads_playlist_id     = EXCLUDED.uploads_playlist_id,
    title                   = EXCLUDED.channel_title,
    processed_at            = CURRENT_TIMESTAMP;
"""


# ---------------------------------------------------------------------------
# CSV Reader
# ---------------------------------------------------------------------------
def load_channels_from_csv(csv_path: str) -> List[Dict[str, Any]]:
    """Read a CSV file and return a list of channel dicts."""
    channels: List[Dict[str, Any]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalise empty strings to None / 0
            channels.append(
                {
                    "channel_id": row["channel_id"].strip(),
                    "channel_title": row["channel_title"].strip(),
                    "country": row.get("country", "").strip() or None,
                    "subscriber_count": int(row.get("subscriber_count", 0) or 0),
                    "total_views": int(row.get("total_views", 0) or 0),
                    "uploads_playlist_id": row.get("uploads_playlist_id", "").strip() or None,
                }
            )
    return channels


# ---------------------------------------------------------------------------
# Step 1: Ensure archive tables exist
# ---------------------------------------------------------------------------
def ensure_archive_tables(conn) -> None:
    """Create archive tables if they don't already exist."""
    with conn.cursor() as cur:
        cur.execute(CREATE_ARCHIVE_TABLES_SQL)
    conn.commit()
    log.info("Archive tables verified / created")


# ---------------------------------------------------------------------------
# Step 2: Snapshot active data into archive tables
# ---------------------------------------------------------------------------
def archive_active_data(conn) -> Dict[str, int]:
    """Copy current active records into archive tables. Returns row counts."""
    counts: Dict[str, int] = {}
    with conn.cursor() as cur:
        # Count existing rows first
        cur.execute("SELECT COUNT(*) FROM channel_stats;")
        counts["channel_stats"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM videos;")
        counts["videos"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM view_timeseries;")
        counts["view_timeseries"] = cur.fetchone()[0]

        if counts["channel_stats"] == 0 and counts["videos"] == 0 and counts["view_timeseries"] == 0:
            log.info("No active data to archive — tables are already empty")
            return counts

        # Archive
        cur.execute(ARCHIVE_CHANNEL_STATS_SQL)
        log.info("Archived %d channel_stats rows", counts["channel_stats"])

        cur.execute(ARCHIVE_VIDEOS_SQL)
        log.info("Archived %d videos rows", counts["videos"])

        cur.execute(ARCHIVE_VIEW_TIMESERIES_SQL)
        log.info("Archived %d view_timeseries rows", counts["view_timeseries"])

    conn.commit()
    return counts


# ---------------------------------------------------------------------------
# Step 3: Clear active tables
# ---------------------------------------------------------------------------
def clear_active_tables(conn) -> None:
    """Delete all rows from active tables (view_timeseries → videos → channel_stats)."""
    with conn.cursor() as cur:
        for sql in TRUNCATE_ACTIVE_SQL:
            cur.execute(sql)
            log.info("Executed: %s", sql.strip())
    conn.commit()
    log.info("Active tables cleared")


# ---------------------------------------------------------------------------
# Step 4: Seed new channels
# ---------------------------------------------------------------------------
def seed_new_channels(conn, channels: List[Dict[str, Any]]) -> int:
    """Upsert the new channel seed list into channel_stats."""
    if not channels:
        log.warning("No channels to seed")
        return 0

    with conn.cursor() as cur:
        execute_batch(cur, UPSERT_CHANNEL_SQL, channels, page_size=200)
    conn.commit()
    log.info("Seeded %d new channels into channel_stats", len(channels))
    return len(channels)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive existing YouTube ETL data and seed a new channel set."
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to CSV file with columns: channel_id, channel_title, country, subscriber_count, total_views, uploads_playlist_id",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print actions without executing database changes.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Load new channels from CSV
    channels = load_channels_from_csv(args.csv)
    log.info("Loaded %d channels from %s", len(channels), args.csv)

    if args.dry_run:
        log.info("=== DRY RUN — no database changes will be made ===")
        log.info("Would archive current channel_stats, videos, view_timeseries")
        log.info("Would clear active tables")
        log.info("Would seed %d new channels:", len(channels))
        for ch in channels[:5]:
            log.info("  %s  %s", ch["channel_id"], ch["channel_title"])
        if len(channels) > 5:
            log.info("  ... and %d more", len(channels) - 5)
        return

    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        log.error("SUPABASE_DB_URL environment variable is not set")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    try:
        log.info("=" * 60)
        log.info("STEP 1/4 — Ensure archive tables exist")
        log.info("=" * 60)
        ensure_archive_tables(conn)

        log.info("=" * 60)
        log.info("STEP 2/4 — Archive active data")
        log.info("=" * 60)
        counts = archive_active_data(conn)

        log.info("=" * 60)
        log.info("STEP 3/4 — Clear active tables")
        log.info("=" * 60)
        clear_active_tables(conn)

        log.info("=" * 60)
        log.info("STEP 4/4 — Seed new channels")
        log.info("=" * 60)
        seeded = seed_new_channels(conn, channels)

        log.info("=" * 60)
        log.info("DONE — Archived %d + %d + %d rows, seeded %d new channels",
                 counts.get("channel_stats", 0),
                 counts.get("videos", 0),
                 counts.get("view_timeseries", 0),
                 seeded)
        log.info("=" * 60)

    except Exception:
        conn.rollback()
        log.exception("Migration failed — rolled back")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
