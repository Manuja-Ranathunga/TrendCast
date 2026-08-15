# Frontend redesign notes

Visual redesign of `frontend/` to match the ViewCast reference app
(`d:\DSEP\ViewCast\` — `index.html`, `styles.css`, `charts.js`, `engine.js`, `app.js`).
Values below are copied **verbatim** from the reference (same names, same numbers)
wherever a direct equivalent exists; sections with no equivalent in the reference are
marked "derived" and built from the same token palette instead of invented from scratch.

Stack, routes, and backend calls are unchanged: Vite + React (JS), React Router, Recharts,
`GET /channels`, `GET /channels/{id}/videos`, `GET /videos/{id}/timeseries`, `POST /forecast`.
`backend/` and `youtube-etl-pipeline/` are untouched. No hand-rolled SVG — all charts stay
Recharts, restyled through its own props.

## What changed

**`src/styles/tokens.css`** (new) — the reference's full `:root` token block copied
verbatim: surface/ink scale, `--series-views/likes/comments`, status tones
(`--good/--warning/--serious/--critical`), `--band-fill`, `--accent-gradient`,
`--glow-accent`, `--blob-a/b`, radii, shadows, `--font-ui`. Same three-tier light /
`prefers-color-scheme: dark` / explicit `[data-theme="dark"]` layering as the reference.
Added `--accent`/`--accent-soft` as aliases of `--series-views`/`--band-fill` (the
reference has no single "brand accent" token — its buttons/links all just use
`--series-views` directly; ours is a named alias of the same value, not a new color).

**`src/index.css`** — rewritten. Sidebar shell (`.app-shell`, `.sidebar`, `.brand`,
`.brand-mark`, `.nav-link` incl. hover/active/left-accent-bar, `.sidebar-footer`,
`.theme-toggle`, `.engine-pill`/`.engine-dot`, `.main`, 860px collapse breakpoint),
typography helpers (`.page-title`, `.page-sub`, `.section-title`, `.eyebrow`), card/grid
(`.card`, `.grid-2/3/4`), buttons (`.btn`, `.btn-primary`, `.btn-ghost`, `.btn-sm`),
`.input`, table (`.table-wrap`, `.data-table`), `.stat-tile`, chart chrome
(`.chart-legend`, `.legend-swatch`), spinner (`.spinner`/`@keyframes spin`), and
`.empty-state` — all copied verbatim, dimensions and colors unchanged.
Decorative `body::before` glow (using `--blob-a/b`) also copied.

Derived (no reference equivalent, built from the same tokens — noted so nothing here
is mistaken for a literal copy):
- `.state-error` — reference is a client-only app with no fetch-error UI; reuses the
  `.empty-state` shape with `--critical`-toned accents.
- `.chart-tooltip-content` — same visual values as the reference's `.chart-tooltip`,
  but without `position: fixed`/manual show-hide, since Recharts owns tooltip
  positioning (the reference hand-tracks `mousemove`, we don't need to).
- `.detail-layout`/`.video-list`/`.video-item` — our channel/video split view has no
  ViewCast equivalent; reskinned with the new tokens, same structure as before.
- `.forecast-form`/`.field`/`.notice-banner` — reference's form is a single hero input
  with no labeled fields or banner component; ours needed both, so `.field` borrows the
  reference's label-sizing conventions and `.notice-banner` derives its background/border
  from a 12%/40% alpha mix of the real `--warning` token (same technique the reference
  uses for `--band-fill`/`--glow-accent`), not an invented color.

**`src/hooks/useTheme.js`** (new) — system → light → dark cycle persisted to
`localStorage`, applying `[data-theme]` on `<html>`. Ports the reference's
`initTheme`/`applyTheme`/`setTheme`/`getTheme` (`app.js`) into a React hook.

**`src/components/Layout.jsx`** — rebuilt as the sidebar shell: brand mark, two nav
links (Explorer, Forecast — the reference's four are Predict/History/Insights/Settings;
we only have two real pages, History/Insights/Settings are deferred per scope), and a
sidebar footer with the theme toggle plus an `.engine-pill` repurposed as an honest
status disclosure — **"Forecast: placeholder model"** — mirroring the reference's own
use of that pill ("Demo model — synthetic data") to disclose non-real output, applied to
our one actually-fake data path (`POST /forecast`'s mock curve) rather than to anything
that isn't.

**`src/components/AsyncState.jsx`** — `LoadingState` now renders the reference's
`.spinner`; `ErrorState`/`EmptyState` use the `.empty-state` icon/heading/body pattern.

**`src/components/ChartTooltip.jsx`** (new) — shared Recharts tooltip content component
using `.chart-tooltip-content`.

**`src/pages/Explorer.jsx`** — `.page-title`/`.page-sub` classes; table already used
`.table-wrap`/`.data-table`, now themed by the copied CSS. Data fetching (`getChannels`)
unchanged.

**`src/pages/ChannelDetail.jsx`** — `.page-title`/`.page-sub`/`.back-link`; added a
4-tile stat row (Tracked videos / Active / Archived / Deleted) computed from the
already-fetched `videos` array — no new API calls, all real counts, no fabricated
numbers. Chart restyled: hairline gridlines, muted axis ticks, `var(--series-views)`
line at `strokeWidth: 2.5`, custom tooltip, legend swatch. Data fetching
(`getChannelVideos`, `getVideoTimeseries`) unchanged.

**`src/pages/Forecast.jsx`** — `.page-title`/`.page-sub`/`.notice-banner` (placeholder
disclosure kept prominent, per standing requirement); added 3 stat-tiles (Day 7/15/30)
computed from the `curve` the backend already returned — no new fetch, these are the
real placeholder-curve values, just presented as tiles instead of only a line. Chart
restyled to match ChannelDetail. `POST /forecast` call unchanged.

## Explicitly not ported

Prediction score, gauge, title/thumbnail checklist, engagement benchmarks,
similar-videos list, tips, and the History/Insights/Settings pages are all generated by
a seeded RNG in the reference (`engine.js`) — synthetic, not real data — and are out of
scope here. None of that content or its components is in this app. Every number
displayed comes from our backend; the forecast curve is real API output, just labeled
as a placeholder because the model behind it isn't trained yet.
