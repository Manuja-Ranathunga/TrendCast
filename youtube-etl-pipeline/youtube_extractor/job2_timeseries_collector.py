"""
================================================================================
job2_timeseries_collector.py — Standalone Script (GitHub Actions)
================================================================================
Schedule  : Every 5 minutes (*/5 * * * *)
Purpose   : Poll due videos, collect REAL time-series metrics from the
            YouTube Data API v3, and adjust polling cadence based on video age.

            Also detects deleted/privatized videos (missing from API response)
            and flags them to prevent infinite re-polling.

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
from typing import Any, Dict, List, Set, Tuple

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

MARK_DELETED_SQL = """
UPDATE videos
SET status = 'deleted_or_private',
    last_polled_at = CURRENT_TIMESTAMP,
    next_poll_at = NULL
WHERE video_id = %(video_id)s;
"""


# ---------------------------------------------------------------------------
# Decay Logic
# ---------------------------------------------------------------------------
def select_interval_hours(age_hours: float) -> float:
    """Choose the next polling interval based on how old the video is.

    Decay tiers:
        0–1 h   → every ~5 min  (0.083 h)  — capture early velocity
        1–2 h   → every 15 min  (0.25 h)
        2+ h    → every 1 hour  (1.0 h)
    """
    if age_hours <= 1:
        return 0.083  # ~5 minutes — high-frequency early capture
    elif age_hours <= 2:
        return 0.25   # 15 minutes
    return 1.0        # 1 hour


# ---------------------------------------------------------------------------
# Step 1: Query due videos from the database
# ---------------------------------------------------------------------------
def query_due_videos(conn) -> List[Dict[str, Any]]:
    """Fetch videos whose next_poll_at has passed."""

    query = """
        SELECT video_id, published_at
        FROM videos
        WHERE next_poll_at <= CURRENT_TIMESTAMP
          AND status = 'active'
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
) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """Fetch real statistics from the YouTube Data API v3 for due videos.

    Uses the APIKeyPool for automatic key rotation on quota exhaustion.
    Videos are requested in batches of 50 (the YouTube API max per request).
    Each batch costs 1 quota unit.

    Returns:
        metrics         — List of stat dicts for videos that were found.
        missing_ids     — Set of video IDs that were requested but NOT returned
                          by the API (deleted / privatized).
    """

    fetched_at = datetime.now(timezone.utc).isoformat()
    metrics: List[Dict[str, Any]] = []
    missing_ids: Set[str] = set()

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

        # Collect IDs the API actually returned in this batch
        returned_ids_in_batch: Set[str] = set()

        for item in response.get("items", []):
            vid = item["id"]
            returned_ids_in_batch.add(vid)
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

        # Detect deleted/privatized: requested but not returned
        batch_missing = set(chunk) - returned_ids_in_batch
        if batch_missing:
            log.warning(
                "Detected %d deleted/private videos in batch: %s",
                len(batch_missing),
                ", ".join(sorted(batch_missing)),
            )
            missing_ids.update(batch_missing)

    log.info("Fetched real metrics for %d / %d videos", len(metrics), len(video_ids))
    if missing_ids:
        log.info("Total deleted/private videos detected: %d", len(missing_ids))
    return metrics, missing_ids


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
def mark_deleted_or_private(conn, missing_ids: Set[str]) -> int:
    """Flag videos that the YouTube API no longer returns (deleted/privatized).

    Sets status = 'deleted_or_private' and next_poll_at = NULL so they are
    never fetched again by query_due_videos.
    """
    if not missing_ids:
        return 0

    rows = [{"video_id": vid} for vid in sorted(missing_ids)]

    with conn.cursor() as cur:
        execute_batch(cur, MARK_DELETED_SQL, rows, page_size=200)
    conn.commit()

    log.info(
        "Flagged %d videos as deleted_or_private: %s",
        len(missing_ids),
        ", ".join(sorted(missing_ids)),
    )
    return len(missing_ids)


def main() -> None:
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        log.error("SUPABASE_DB_URL environment variable is not set")
        sys.exit(1)

    log.info("Job 2 — Timeseries Collector starting")

    # Initialise the YouTube API key pool from environment
    key_pool = APIKeyPool.from_env()

    conn = psycopg2.connect(db_url)
    try:
        # Step 1: Get due videos
        due_videos = query_due_videos(conn)

        if not due_videos:
            log.info("No videos are due for polling — exiting")
            return

        # Step 2: Fetch REAL stats from YouTube API
        metrics, missing_ids = fetch_youtube_stats(due_videos, key_pool)

        # Step 2b: Flag deleted/privatized videos so they stop clogging polls
        if missing_ids:
            mark_deleted_or_private(conn, missing_ids)

        # Step 3: Persist and apply decay
        total = apply_decay_and_update(conn, metrics)
        log.info("Job 2 complete — %d total rows processed", total)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
