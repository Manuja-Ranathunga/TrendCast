"""
================================================================================
job2_timeseries_collector.py — Standalone Script (GitHub Actions)
================================================================================
Schedule  : Every 15 minutes (*/15 * * * *)
Purpose   : Poll due videos, collect REAL time-series metrics from the
            YouTube Data API v3, and adjust polling cadence based on video age.

Environment Variables:
    SUPABASE_DB_URL    — PostgreSQL connection string
    YOUTUBE_API_KEYS   — Comma-separated YouTube Data API v3 keys (preferred)
    YOUTUBE_API_KEY    — Single YouTube API key (fallback)
================================================================================
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import psycopg2
from googleapiclient.errors import HttpError

# Ensure sibling modules (key_pool.py) are importable when run as a standalone script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from key_pool import APIKeyPool, AllKeysExhaustedError

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
# SQL Templates
# ---------------------------------------------------------------------------
INSERT_TIMESERIES_SQL = """
INSERT INTO view_timeseries (
    video_id,
    scraped_at,
    view_count,
    like_count,
    comment_count
) VALUES (
    %(video_id)s,
    %(scraped_at)s,
    %(view_count)s,
    %(like_count)s,
    %(comment_count)s
);
"""

UPDATE_VIDEO_POLLS_SQL = """
UPDATE videos
SET last_polled_at = %(last_polled_at)s,
    next_poll_at = %(next_poll_at)s,
    current_interval_hours = %(current_interval_hours)s
WHERE video_id = %(video_id)s;
"""

ENSURE_MIGRATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS _etl_migrations (
    migration_name  VARCHAR(128)    PRIMARY KEY,
    applied_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
"""

MIGRATION_FLAG = "archive_mock_timeseries_v1"

ARCHIVE_MOCK_DATA_SQL = """
INSERT INTO view_timeseries_archive
    (original_id, video_id, scraped_at, view_count, like_count, comment_count)
SELECT
    id, video_id, scraped_at, view_count, like_count, comment_count
FROM view_timeseries;
"""

CLEAR_TIMESERIES_SQL = """
TRUNCATE view_timeseries;
"""


# ---------------------------------------------------------------------------
# Decay Logic
# ---------------------------------------------------------------------------
def select_interval_hours(age_hours: float) -> int:
    """Choose the next polling interval based on how old the video is."""
    if age_hours < 24:
        return 1
    if age_hours < 7 * 24:
        return 6
    if age_hours < 30 * 24:
        return 24
    return 168


# ---------------------------------------------------------------------------
# Step 1: Query due videos from the database
# ---------------------------------------------------------------------------
def query_due_videos(conn) -> List[Dict[str, Any]]:
    """Fetch videos whose next_poll_at has passed."""

    query = """
        SELECT video_id, published_at
        FROM videos
        WHERE next_poll_at <= CURRENT_TIMESTAMP
        ORDER BY next_poll_at ASC, video_id ASC
    """

    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    due_videos = [
        {
            "video_id": row[0],
            "published_at": row[1].isoformat() if hasattr(row[1], "isoformat") else row[1],
        }
        for row in rows
    ]

    log.info("Found %d due videos", len(due_videos))
    return due_videos


# ---------------------------------------------------------------------------
# Step 2: Fetch REAL YouTube stats via YouTube Data API v3
# ---------------------------------------------------------------------------
def fetch_youtube_stats(
    due_videos: List[Dict[str, Any]],
    key_pool: APIKeyPool,
) -> List[Dict[str, Any]]:
    """Fetch real statistics from the YouTube Data API v3 for due videos.

    Uses the APIKeyPool for automatic key rotation on quota exhaustion.
    Videos are requested in batches of 50 (the YouTube API max per request).
    Each batch costs 1 quota unit.
    """

    fetched_at = datetime.now(timezone.utc).isoformat()
    metrics: List[Dict[str, Any]] = []

    # Build a lookup so we can pair API results back to published_at
    video_lookup = {v["video_id"]: v["published_at"] for v in due_videos}
    video_ids = list(video_lookup.keys())

    # YouTube API accepts up to 50 video IDs per request
    BATCH_SIZE = 50

    for i in range(0, len(video_ids), BATCH_SIZE):
        chunk = video_ids[i : i + BATCH_SIZE]
        ids_csv = ",".join(chunk)

        log.info(
            "Requesting stats batch %d–%d of %d videos",
            i + 1,
            min(i + BATCH_SIZE, len(video_ids)),
            len(video_ids),
        )

        try:
            response = key_pool.execute_with_rotation(
                lambda svc, ids=ids_csv: svc.videos().list(part="statistics", id=ids)
            )
        except AllKeysExhaustedError:
            log.error("All YouTube API keys exhausted — aborting remaining batches")
            break
        except HttpError as exc:
            log.error("YouTube API error (non-quota): %s", exc)
            continue  # skip this batch, try the next

        for item in response.get("items", []):
            vid = item["id"]
            stats = item.get("statistics", {})

            metrics.append(
                {
                    "video_id": vid,
                    "published_at": video_lookup.get(vid, ""),
                    "scraped_at": fetched_at,
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "comment_count": int(stats.get("commentCount", 0)),
                }
            )

    log.info("Fetched real metrics for %d / %d videos", len(metrics), len(video_ids))
    return metrics


from psycopg2.extras import execute_batch


# ---------------------------------------------------------------------------
# Step 3: Persist metrics and apply decay-polling updates
# ---------------------------------------------------------------------------
def apply_decay_and_update(conn, metrics: List[Dict[str, Any]]) -> int:
    """Insert timeseries rows and recalculate polling cadence for each video."""

    if not metrics:
        log.info("No metrics to persist")
        return 0

    # Sort deterministically by video_id to prevent PostgreSQL deadlocks with Job 1
    metrics.sort(key=lambda x: x["video_id"])

    now = datetime.now(timezone.utc)
    ts_rows: List[Dict[str, Any]] = []
    poll_rows: List[Dict[str, Any]] = []

    for metric in metrics:
        # Parse published_at
        published_at_raw = metric["published_at"]
        if isinstance(published_at_raw, str):
            published_at = datetime.fromisoformat(
                published_at_raw.replace("Z", "+00:00")
            )
        else:
            published_at = published_at_raw

        age_hours = (now - published_at).total_seconds() / 3600.0
        current_interval_hours = select_interval_hours(age_hours)
        next_poll_at = now + timedelta(hours=current_interval_hours)

        ts_rows.append({
            "video_id": metric["video_id"],
            "scraped_at": metric["scraped_at"],
            "view_count": metric["view_count"],
            "like_count": metric["like_count"],
            "comment_count": metric["comment_count"],
        })

        poll_rows.append({
            "video_id": metric["video_id"],
            "last_polled_at": now.isoformat(),
            "next_poll_at": next_poll_at.isoformat(),
            "current_interval_hours": current_interval_hours,
        })

    with conn.cursor() as cur:
        execute_batch(cur, INSERT_TIMESERIES_SQL, ts_rows, page_size=200)
        execute_batch(cur, UPDATE_VIDEO_POLLS_SQL, poll_rows, page_size=200)

    conn.commit()
    log.info("Persisted %d time-series rows and updated polling cadence", len(metrics))
    return len(metrics)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def archive_and_clear_mock_data(conn) -> None:
    """One-time migration: move all existing mock/simulated timeseries rows
    into view_timeseries_archive, then truncate the live table.

    Uses a database-level flag in _etl_migrations so it runs exactly once,
    even across multiple deployments or runners.
    """
    with conn.cursor() as cur:
        # Ensure the migrations flag table exists
        cur.execute(ENSURE_MIGRATIONS_TABLE_SQL)

        # Check if this migration has already been applied
        cur.execute(
            "SELECT 1 FROM _etl_migrations WHERE migration_name = %s;",
            (MIGRATION_FLAG,),
        )
        if cur.fetchone() is not None:
            log.info("Migration '%s' already applied — skipping archive step", MIGRATION_FLAG)
            conn.commit()
            return

        # Check if there is anything to archive
        cur.execute("SELECT COUNT(*) FROM view_timeseries;")
        row_count = cur.fetchone()[0]

        if row_count > 0:
            # Archive existing rows
            cur.execute(ARCHIVE_MOCK_DATA_SQL)
            archived = cur.rowcount
            log.info("Archived %d mock timeseries rows into view_timeseries_archive", archived)

            # Clear the live table
            cur.execute(CLEAR_TIMESERIES_SQL)
            log.info("Truncated view_timeseries table")
        else:
            log.info("view_timeseries is already empty — nothing to archive")

        # Record that this migration is done
        cur.execute(
            "INSERT INTO _etl_migrations (migration_name) VALUES (%s);",
            (MIGRATION_FLAG,),
        )
        log.info("Migration '%s' recorded — will not run again", MIGRATION_FLAG)

    conn.commit()


def main() -> None:
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        log.error("SUPABASE_DB_URL environment variable is not set")
        sys.exit(1)

    log.info("Job 2 — Timeseries Collector starting")

    # Debug: check which API key env vars are present
    has_keys = bool(os.environ.get("YOUTUBE_API_KEYS", "").strip())
    has_key = bool(os.environ.get("YOUTUBE_API_KEY", "").strip())
    log.info(
        "API key env check — YOUTUBE_API_KEYS present: %s, YOUTUBE_API_KEY present: %s",
        has_keys,
        has_key,
    )

    # Initialise the YouTube API key pool from environment
    key_pool = APIKeyPool.from_env()

    conn = psycopg2.connect(db_url)
    try:
        # Step 0: Archive old mock data and clear the live table
        archive_and_clear_mock_data(conn)

        # Step 1: Get due videos
        due_videos = query_due_videos(conn)

        if not due_videos:
            log.info("No videos are due for polling — exiting")
            return

        # Step 2: Fetch REAL stats from YouTube API
        metrics = fetch_youtube_stats(due_videos, key_pool)

        # Step 3: Persist and apply decay
        total = apply_decay_and_update(conn, metrics)
        log.info("Job 2 complete — %d total rows processed", total)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
