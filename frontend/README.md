# TrendCast Frontend

React (Vite) frontend for TrendCast — explore tracked YouTube channels, inspect
real view trajectories collected by the ETL pipeline, and generate placeholder
30-day forecasts for planned uploads.

## Prerequisites

- Node.js 18+
- The `backend/` FastAPI service running and reachable (see `backend/README.md`
  if present, or run it with `uvicorn main:app --reload` from `backend/`).

## Setup

```bash
cd frontend
npm install
cp .env.example .env   # adjust VITE_API_BASE_URL if the backend isn't on 127.0.0.1:8000
npm run dev
```

The app runs at `http://localhost:5173` by default. The backend's CORS config
must allow that origin (it does, out of the box).

## Environment variables

| Variable              | Description                          | Default                  |
| ---------------------- | ------------------------------------- | ------------------------- |
| `VITE_API_BASE_URL`   | Base URL of the FastAPI backend       | `http://127.0.0.1:8000`  |

## Scripts

- `npm run dev` — start the Vite dev server
- `npm run build` — production build to `dist/`
- `npm run preview` — preview the production build locally
- `npm run lint` — run oxlint

## Structure

- `src/api/client.js` — all backend fetch calls live here
- `src/hooks/useFetch.js` — shared loading/error/data hook for GET requests
- `src/components/` — shared layout and loading/error/empty state components
- `src/pages/` — one component per route (Explorer, ChannelDetail, Forecast)
- `src/utils/format.js` — number/date formatting helpers

## Pages

- **Explorer (`/`)** — table of all channels with subscriber/view counts and size tier.
- **Channel detail (`/channels/:channelId`)** — a channel's videos; select one to
  see its real, collected view-count trajectory as a line chart.
- **Forecast (`/forecast`)** — submit a planned upload's title, thumbnail URL,
  and scheduled time to get a 30-day projected view curve. Currently returns a
  hardcoded mock curve from the backend — the real model isn't wired up yet.
