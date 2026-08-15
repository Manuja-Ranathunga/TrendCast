# trendcast-githubactions

## Database (Supabase / PostgreSQL)

Schema is defined in [youtube-etl-pipeline/postgres/init/01_schema.sql](youtube-etl-pipeline/postgres/init/01_schema.sql), applied automatically on first container start. A second migration, [02_archive_and_switch_channels.sql](youtube-etl-pipeline/postgres/init/02_archive_and_switch_channels.sql), adds `channel_stats_archive`, `videos_archive`, and `view_timeseries_archive` tables that snapshot rows before a channel-set rotation — mirror copies of the core tables below plus `archive_id`/`archived_at`.

### Connection pattern

- Connection string comes from the `SUPABASE_DB_URL` environment variable (a standard Postgres connection URL).
- ETL jobs connect with plain `psycopg2.connect(db_url)` — see [youtube_extractor/job2_timeseries_collector.py](youtube-etl-pipeline/youtube_extractor/job2_timeseries_collector.py) `main()`.
- Bulk writes use `psycopg2.extras.execute_batch` with named-parameter SQL templates (`%(name)s`), followed by an explicit `conn.commit()`.
- When writing to multiple tables that Job 1 (channel ingestion) also touches, rows are sorted deterministically by primary key (e.g. `video_id`) before the batch write to avoid Postgres deadlocks between concurrently running jobs.
- A **new FastAPI backend is being built in `backend/`** that will read from this same Supabase database — reuse `SUPABASE_DB_URL` and the same connection pattern rather than introducing a second DB config convention.

### Core tables

**`channel_stats`** — one row per YouTube channel (PK: `channel_id`, format `UCxxxxxxxxxxxxxxxxxxxxxx`).
- `channel_title`, `channel_description`, `published_at` (channel creation time), `country` (ISO 3166-1 alpha-2)
- `total_views`, `subscriber_count` (both `BIGINT`, channels can exceed 2^31), `video_count`
- `processed_at` — last successful extraction timestamp; `created_at` — first insert time
- Extension columns (added via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`): `title` (backfilled copy of `channel_title`), `tier_category`, `uploads_playlist_id`, `last_checked_at`
- Checks: `total_views`, `subscriber_count`, `video_count` all `>= 0`
- Indexes: `subscriber_count DESC`, `processed_at DESC`, `total_views DESC`, `country`, `last_checked_at DESC`

**`videos`** — polling queue / status per video (PK: `video_id`).
- `channel_id` FK → `channel_stats.channel_id` (`ON DELETE CASCADE`)
- `published_at`, `status` (`active` | `archived` | `deleted`, default `active`)
- `last_polled_at`, `next_poll_at` — drive the polling queue
- `current_interval_hours` (`NUMERIC(5,2)`, must be `> 0`) — current polling cadence for this video
- Indexes: `next_poll_at`, `(status, next_poll_at)` for queue picks, `channel_id`

**`view_timeseries`** — raw metric snapshots, one row per poll (PK: `id BIGSERIAL`).
- `video_id` FK → `videos.video_id` (`ON DELETE CASCADE`)
- `scraped_at`, `view_count`, `like_count`, `comment_count` (all `>= 0`)
- Indexes: `(video_id, scraped_at DESC)`, `scraped_at DESC`

**`channel_stats_enriched`** (VIEW, not a table) — wraps `channel_stats` with computed engagement KPIs:
- `avg_views_per_video` = `total_views / video_count`
- `views_per_subscriber` = `total_views / subscriber_count`
- `engagement_ratio` = `(subscriber_count / total_views) * 100` (%)
- `size_tier` — categorical bucket from `subscriber_count`: Micro (<1K), Small (1K–10K), Mid (10K–100K), Large (100K–1M), Mega (1M+)
- `channel_age_days` — days since `published_at`
- All ratio calculations are divide-by-zero guarded (`CASE WHEN ... > 0`)

### Polling cadence (Job 2)

`job2_timeseries_collector.py` polls due videos every 5 minutes and adjusts `current_interval_hours` by video age (`select_interval_hours`):
- age ≤ 1h → poll every ~5 min
- age 1–2h → poll every 15 min
- age > 2h → poll every 1 hour

Videos missing from the YouTube API response (deleted/privatized) are flagged `status = 'deleted'` with `next_poll_at = NULL` so they drop out of the queue. Note `videos.status` is `VARCHAR(16)` — keep any new status values within that limit.
