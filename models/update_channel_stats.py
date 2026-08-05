"""
update_channel_stats.py

Updates ONLY these columns in channel_stats.csv (fills nulls / adds if missing):
    tier_category, video_count, channel_description, published_at

All other existing columns/values are left untouched.

tier_category is derived as the most common YouTube video category_id
among that channel's videos, read from video_category_map.csv
(produced by update_video_data.py). Run that script first.

Install first:
    pip install google-api-python-client pandas

Usage:
    python update_channel_stats.py
"""

import time
import pandas as pd
from googleapiclient.discovery import build

# ---- CONFIG ----
API_KEY = "AIzaSyDFdHqWi2gfECiIDpJgqYmEbWZN797CF_g"
INPUT_CSV = "D:/DSEP/trendcast-githubactions/models/channel_stats_rows.csv"
OUTPUT_CSV = "channel_stats_updated.csv"
CATEGORY_MAP_CSV = "video_category_map.csv"  # output of update_video_data.py
BATCH_SIZE = 50  # max allowed by channels.list per request

youtube = build("youtube", "v3", developerKey=API_KEY)


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def fetch_channel_batch(channel_ids):
    """Returns dict: channel_id -> {description, published_at, video_count}"""
    result = {}
    resp = youtube.channels().list(
        part="snippet,statistics",
        id=",".join(channel_ids)
    ).execute()

    for item in resp.get("items", []):
        cid = item["id"]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})

        result[cid] = {
            "channel_description": snippet.get("description"),
            "published_at": snippet.get("publishedAt"),
            "video_count": stats.get("videoCount"),
        }
    return result


def build_tier_category_map(category_map_csv):
    """channel_id -> most frequent video category_id"""
    try:
        cat_df = pd.read_csv(category_map_csv)
    except FileNotFoundError:
        print(f"Warning: {category_map_csv} not found. tier_category will be left empty.")
        return {}

    cat_df = cat_df.dropna(subset=["category_id"])
    if cat_df.empty:
        return {}

    mode_per_channel = (
        cat_df.groupby("channel_id")["category_id"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else None)
    )
    return mode_per_channel.to_dict()


def main():
    df = pd.read_csv(INPUT_CSV)

    for col in ["tier_category", "video_count", "channel_description", "published_at"]:
        if col not in df.columns:
            df[col] = None

    channel_ids = df["channel_id"].dropna().astype(str).tolist()
    all_results = {}
    total_batches = (len(channel_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    for i, batch in enumerate(chunks(channel_ids, BATCH_SIZE), start=1):
        print(f"Fetching channel batch {i}/{total_batches} ({len(batch)} ids)...")
        try:
            batch_result = fetch_channel_batch(batch)
            all_results.update(batch_result)
        except Exception as e:
            print(f"  Batch {i} failed: {e}")
        time.sleep(0.2)

    tier_map = build_tier_category_map(CATEGORY_MAP_CSV)

    for idx, row in df.iterrows():
        cid = str(row["channel_id"])
        data = all_results.get(cid)
        if data:
            df.at[idx, "channel_description"] = data["channel_description"]
            df.at[idx, "published_at"] = data["published_at"]
            df.at[idx, "video_count"] = data["video_count"]

        if cid in tier_map:
            df.at[idx, "tier_category"] = tier_map[cid]

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
