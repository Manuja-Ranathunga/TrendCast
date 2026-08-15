from typing import List

from fastapi import FastAPI

from db import get_cursor
from models import ChannelStatsEnriched, ForecastPoint, ForecastRequest, Video, ViewTimeseries

app = FastAPI(title="Trendcast API")

# PLACEHOLDER: hardcoded mock cumulative view curve, standing in until the
# real forecasting model is trained and wired up. Ignores the request body.
MOCK_CUMULATIVE_VIEW_CURVE = [
    1200, 2600, 4300, 6100, 8000, 9800, 11500,
    13100, 14600, 16000, 17300, 18500, 19600, 20600,
    21500, 22300, 23000, 23600, 24100, 24550, 24950,
    25300, 25600, 25850, 26050, 26200, 26320, 26410,
    26470, 26500,
]

TIMESERIES_BY_VIDEO_SQL = """
    SELECT
        id,
        video_id,
        scraped_at,
        view_count,
        like_count,
        comment_count
    FROM view_timeseries
    WHERE video_id = %(video_id)s
    ORDER BY scraped_at ASC
"""

VIDEOS_BY_CHANNEL_SQL = """
    SELECT
        video_id,
        channel_id,
        published_at,
        status,
        last_polled_at,
        next_poll_at,
        current_interval_hours,
        created_at
    FROM videos
    WHERE channel_id = %(channel_id)s
    ORDER BY published_at DESC
"""

CHANNELS_ENRICHED_SQL = """
    SELECT
        channel_id,
        channel_title,
        channel_description,
        published_at,
        country,
        total_views,
        subscriber_count,
        video_count,
        processed_at,
        created_at,
        avg_views_per_video,
        views_per_subscriber,
        engagement_ratio,
        size_tier,
        channel_age_days
    FROM channel_stats_enriched
"""


@app.get("/health")
def health():
    with get_cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    return {"status": "ok", "db": "connected"}


@app.get("/channels", response_model=List[ChannelStatsEnriched])
def get_channels():
    with get_cursor() as cur:
        cur.execute(CHANNELS_ENRICHED_SQL)
        columns = [col.name for col in cur.description]
        rows = cur.fetchall()
    return [dict(zip(columns, row)) for row in rows]


@app.get("/videos/{video_id}/timeseries", response_model=List[ViewTimeseries])
def get_video_timeseries(video_id: str):
    with get_cursor() as cur:
        cur.execute(TIMESERIES_BY_VIDEO_SQL, {"video_id": video_id})
        columns = [col.name for col in cur.description]
        rows = cur.fetchall()
    return [dict(zip(columns, row)) for row in rows]


@app.post("/forecast", response_model=List[ForecastPoint])
def forecast(request: ForecastRequest):
    # PLACEHOLDER: returns the hardcoded mock curve regardless of input.
    # Replace with a call to the real forecasting model once it exists.
    return [
        {"day": day, "views": views}
        for day, views in enumerate(MOCK_CUMULATIVE_VIEW_CURVE, start=1)
    ]


@app.get("/channels/{channel_id}/videos", response_model=List[Video])
def get_channel_videos(channel_id: str):
    with get_cursor() as cur:
        cur.execute(VIDEOS_BY_CHANNEL_SQL, {"channel_id": channel_id})
        columns = [col.name for col in cur.description]
        rows = cur.fetchall()
    return [dict(zip(columns, row)) for row in rows]
