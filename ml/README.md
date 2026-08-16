# ml/

Data audit and extraction for the 7-day view-trajectory model. Everything
here is **read-only** against the Supabase/Postgres database — no writes.

## Setup

```
pip install -r ml/requirements.txt
```

Connects using `SUPABASE_DB_URL`, loaded from `backend/.env` (same variable
and `.env` file the backend and ETL jobs use — nothing to configure here).

## Scripts

- **`audit_data.py`** — prints a coverage / data-quality / usable-set summary
  to stdout. Run this first to see how much training data currently exists.

  ```
  python ml/audit_data.py
  ```

- **`extract_dataset.py`** — writes the usable video set to
  `ml/data/videos.csv` (one row per video, joined with `channel_stats_enriched`
  channel features) and `ml/data/view_timeseries.csv` (long-format
  observations for those videos).

  ```
  python ml/extract_dataset.py
  ```

- **`common.py`** — shared read-only DB access and the "usable video"
  definition, used by both scripts so the audit numbers and the extracted
  dataset always agree.

## "Usable" video definition

A video is included in the training set if it meets all of:

- observation span (published_at → latest scraped_at) >= 7 days
- no `view_timeseries` row with `scraped_at < published_at` (old broken
  `published_at` data)
- non-null `title` and `thumbnail_url`
- monotonically non-decreasing `view_count` over time

`ml/data/` (the CSV output) is gitignored — regenerate it locally with
`extract_dataset.py` rather than committing it.
