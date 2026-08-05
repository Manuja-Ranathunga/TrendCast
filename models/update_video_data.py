"""
update_video_data.py

Updates ONLY these columns in videos_rows.csv (adds them if missing):
    video_title, video_description, video_thumbnail, video_tags

All other existing columns/values are left untouched.

Also writes a side file: video_category_map.csv (video_id, channel_id, category_id)
-> used by update_channel_stats.py to derive tier_category per channel.

Install first:
    pip install google-api-python-client pandas

Usage:
    python update_video_data.py
"""

import time
import pandas as pd
from googleapiclient.discovery import build

# ---- CONFIG ----
API_KEY = "AIzaSyDFdHqWi2gfECiIDpJgqYmEbWZN797CF_g"
INPUT_CSV = "D:/DSEP/trendcast-githubactions/models/videos_rows.csv"
OUTPUT_CSV = "videos_rows_updated.csv"
CATEGORY_MAP_CSV = "video_category_map.csv"
BATCH_SIZE = 50  # max allowed by videos.list per request

youtube = build("youtube", "v3", developerKey=API_KEY)


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def fetch_video_batch(video_ids):
    """Returns dict: video_id -> {title, description, thumbnail, tags, category_id}"""
    result = {}
    resp = youtube.videos().list(
        part="snippet",
        id=",".join(video_ids)
    ).execute()

    for item in resp.get("items", []):
        vid = item["id"]
        snippet = item.get("snippet", {})
        thumbs = snippet.get("thumbnails", {})
        thumb_url = (
            thumbs.get("high", {}).get("url")
            or thumbs.get("medium", {}).get("url")
            or thumbs.get("default", {}).get("url")
        )
        tags = snippet.get("tags", [])

        result[vid] = {
            "video_title": snippet.get("title"),
            "video_description": snippet.get("description"),
            "video_thumbnail": thumb_url,
            "video_tags": "|".join(tags) if tags else None,
            "category_id": snippet.get("categoryId"),
        }
    return result


def main():
    df = pd.read_csv(INPUT_CSV)

    # add the 4 target columns if they don't already exist
    for col in ["video_title", "video_description", "video_thumbnail", "video_tags"]:
        if col not in df.columns:
            df[col] = None

    video_ids = df["video_id"].dropna().astype(str).tolist()
    category_rows = []

    all_results = {}
    total_batches = (len(video_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    for i, batch in enumerate(chunks(video_ids, BATCH_SIZE), start=1):
        print(f"Fetching video batch {i}/{total_batches} ({len(batch)} ids)...")
        try:
            batch_result = fetch_video_batch(batch)
            all_results.update(batch_result)
        except Exception as e:
            print(f"  Batch {i} failed: {e}")
        time.sleep(0.2)  # small delay to be gentle on quota/rate limits

    # apply results back into dataframe, row by row, only touching the 4 target columns
    for idx, row in df.iterrows():
        vid = str(row["video_id"])
        data = all_results.get(vid)
        if not data:
            continue  # video not returned (deleted/private/invalid) -> leave existing values as-is
        df.at[idx, "video_title"] = data["video_title"]
        df.at[idx, "video_description"] = data["video_description"]
        df.at[idx, "video_thumbnail"] = data["video_thumbnail"]
        df.at[idx, "video_tags"] = data["video_tags"]

        category_rows.append({
            "video_id": vid,
            "channel_id": row.get("channel_id"),
            "category_id": data["category_id"],
        })

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved: {OUTPUT_CSV}")

    pd.DataFrame(category_rows).to_csv(CATEGORY_MAP_CSV, index=False)
    print(f"Saved: {CATEGORY_MAP_CSV}")


if __name__ == "__main__":
    main()
