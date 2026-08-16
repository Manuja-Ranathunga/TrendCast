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

  return (
    <div>
      <div className="page-header">
        <Link to="/" className="back-link">
          ← Back to channels
        </Link>
        <h1>Channel videos</h1>
        <p className="page-subtitle">{channelId}</p>
      </div>

      {videosLoading && <LoadingState label="Loading videos…" />}
      {!videosLoading && videosError && (
        <ErrorState error={videosError} onRetry={retryVideos} />
      )}
      {!videosLoading && !videosError && videos?.length === 0 && (
        <EmptyState label="This channel has no tracked videos yet." />
      )}

      {!videosLoading && !videosError && videos?.length > 0 && (
        <div className="detail-layout">
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

          <div className="chart-panel">
            {!selectedVideoId && (
              <EmptyState label="Select a video to view its view trajectory." />
            )}

            {selectedVideoId && timeseriesLoading && (
              <LoadingState label="Loading timeseries…" />
            )}

            {selectedVideoId && !timeseriesLoading && timeseriesError && (
              <ErrorState error={timeseriesError} onRetry={retryTimeseries} />
            )}

            {selectedVideoId && !timeseriesLoading && !timeseriesError && timeseries?.length === 0 && (
              <EmptyState label="No timeseries data has been collected for this video yet." />
            )}

            {selectedVideoId && !timeseriesLoading && !timeseriesError && timeseries?.length > 0 && (
              <ResponsiveContainer width="100%" height={360}>
                <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis
                    dataKey="scraped_at_label"
                    tick={{ fontSize: 12 }}
                    minTickGap={24}
                  />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    tickFormatter={formatCompactNumber}
                    width={56}
                  />
                  <Tooltip
                    formatter={(value) => formatCompactNumber(value)}
                    labelFormatter={(label) => label}
                  />
                  <Line
                    type="monotone"
                    dataKey="view_count"
                    stroke="var(--accent)"
                    strokeWidth={2}
                    dot={chartData.length <= 60}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
