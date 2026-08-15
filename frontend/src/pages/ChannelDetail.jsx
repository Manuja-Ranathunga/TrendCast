import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getChannelVideos, getVideoTimeseries } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import { ChartTooltip } from '../components/ChartTooltip'
import { formatCompactNumber, formatDateTime } from '../utils/format'

export function ChannelDetail() {
  const { channelId } = useParams()
  const [selectedVideoId, setSelectedVideoId] = useState(null)

  const videosFetcher = useCallback(() => getChannelVideos(channelId), [channelId])
  const {
    data: videos,
    error: videosError,
    loading: videosLoading,
    retry: retryVideos,
  } = useFetch(videosFetcher, [channelId])

  const timeseriesFetcher = useCallback(
    () => getVideoTimeseries(selectedVideoId),
    [selectedVideoId],
  )
  const {
    data: timeseries,
    error: timeseriesError,
    loading: timeseriesLoading,
    retry: retryTimeseries,
  } = useFetch(timeseriesFetcher, [selectedVideoId], { enabled: Boolean(selectedVideoId) })

  const chartData = (timeseries || []).map((point) => ({
    ...point,
    scraped_at_label: formatDateTime(point.scraped_at),
  }))

  const statusCounts = (videos || []).reduce(
    (acc, v) => ({ ...acc, [v.status]: (acc[v.status] || 0) + 1 }),
    {},
  )

  return (
    <div>
      <div className="page-header">
        <Link to="/" className="back-link">
          ← Back to channels
        </Link>
        <h1 className="page-title">Channel videos</h1>
        <p className="page-sub">{channelId}</p>
      </div>

      {videosLoading && <LoadingState label="Loading videos…" />}
      {!videosLoading && videosError && (
        <ErrorState error={videosError} onRetry={retryVideos} />
      )}
      {!videosLoading && !videosError && videos?.length === 0 && (
        <EmptyState label="This channel has no tracked videos yet." />
      )}

      {!videosLoading && !videosError && videos?.length > 0 && (
        <>
          <div className="grid grid-4 mt-16">
            <div className="card stat-tile">
              <div className="st-top"><span className="st-label">Tracked videos</span></div>
              <div className="st-value mono">{videos.length}</div>
            </div>
            <div className="card stat-tile">
              <div className="st-top"><span className="st-label">Active</span></div>
              <div className="st-value mono">{statusCounts.active || 0}</div>
            </div>
            <div className="card stat-tile">
              <div className="st-top"><span className="st-label">Archived</span></div>
              <div className="st-value mono">{statusCounts.archived || 0}</div>
            </div>
            <div className="card stat-tile">
              <div className="st-top"><span className="st-label">Deleted</span></div>
              <div className="st-value mono">{statusCounts.deleted || 0}</div>
            </div>
          </div>

          <div className="detail-layout mt-16">
            <div className="card">
              <div className="section-title">Videos</div>
              <ul className="video-list">
                {videos.map((video) => (
                  <li key={video.video_id}>
                    <button
                      type="button"
                      className={video.video_id === selectedVideoId ? 'video-item active' : 'video-item'}
                      onClick={() => setSelectedVideoId(video.video_id)}
                    >
                      <span className="video-id">{video.video_id}</span>
                      <span className="video-meta">
                        Published {formatDateTime(video.published_at)} · {video.status}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>

            <div className="card chart-panel">
              <div className="section-title">View trajectory</div>

              {!selectedVideoId && (
                <EmptyState label="Select a video to view its view trajectory." />
              )}

              {selectedVideoId && timeseriesLoading && <LoadingState label="Loading timeseries…" />}

              {selectedVideoId && !timeseriesLoading && timeseriesError && (
                <ErrorState error={timeseriesError} onRetry={retryTimeseries} />
              )}

              {selectedVideoId && !timeseriesLoading && !timeseriesError && timeseries?.length === 0 && (
                <EmptyState label="No timeseries data has been collected for this video yet." />
              )}

              {selectedVideoId && !timeseriesLoading && !timeseriesError && timeseries?.length > 0 && (
                <>
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                      <CartesianGrid vertical={false} stroke="var(--hairline)" />
                      <XAxis
                        dataKey="scraped_at_label"
                        tick={{ fontSize: 10.5, fill: 'var(--muted)' }}
                        axisLine={{ stroke: 'var(--hairline)' }}
                        tickLine={false}
                        minTickGap={24}
                      />
                      <YAxis
                        tick={{ fontSize: 10.5, fill: 'var(--muted)' }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={formatCompactNumber}
                        width={44}
                      />
                      <Tooltip
                        content={<ChartTooltip valueLabel="Views" formatter={formatCompactNumber} />}
                      />
                      <Line
                        type="monotone"
                        dataKey="view_count"
                        stroke="var(--series-views)"
                        strokeWidth={2.5}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        dot={chartData.length <= 60 ? { r: 3, fill: 'var(--series-views)', strokeWidth: 0 } : false}
                        activeDot={{ r: 5, fill: 'var(--series-views)', stroke: 'var(--surface)', strokeWidth: 2 }}
                        isAnimationActive={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                  <div className="chart-legend">
                    <span className="legend-item">
                      <span className="legend-swatch line" style={{ background: 'var(--series-views)' }} />
                      Views
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
