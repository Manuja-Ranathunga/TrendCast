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

- **`fit_curves.py`** — reads `ml/data/view_timeseries.csv` and
  `ml/data/videos.csv`, resamples each video onto a regular 0-168h grid
  (hourly for 48h, then every 6h), fits a saturating exponential
  `V(t) = V_inf * (1 - exp(-t/tau))` per video, and writes
  `ml/data/curve_params.csv` plus a diagnostics report to stdout (fit
  success rate, R² distribution, and an identifiability check for videos
  that haven't visibly saturated within 7 days). Local file I/O only, no DB.

  ```
  python ml/fit_curves.py
  ```

- **`plot_fits.py`** — samples 12 videos across the R² range (worst /
  median / best) and saves `ml/data/fit_examples.png`, observed points
  against the fitted curve.

  ```
  python ml/plot_fits.py
  ```

## "Usable" video definition

A video is included in the training set if it meets all of:

- observation span (published_at → latest scraped_at) >= 7 days
- no `view_timeseries` row with `scraped_at < published_at` (old broken
  `published_at` data)
- non-null `title` and `thumbnail_url`
- largest single downward view-count dip <= 5% of the pre-dip value (YouTube
  legitimately revises counts down when filtering spam; retained videos have
  their `view_count` repaired to a running maximum rather than excluded)
- largest observation gap within the first 7 days <= 24h

See `common.py`'s `compute_audit()` for the exact stepwise filter pipeline
and `audit_data.py` for the full diagnostics (including threshold
sensitivity and the channel distribution of the usable set).

`ml/data/` (the CSV/PNG output) is gitignored — regenerate it locally with
`extract_dataset.py`, `fit_curves.py`, and `plot_fits.py` rather than
committing it.
