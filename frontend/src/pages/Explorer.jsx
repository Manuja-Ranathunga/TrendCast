import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getChannels } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import { formatCompactNumber, slugify } from '../utils/format'

export function Explorer() {
  const navigate = useNavigate()
  const fetcher = useCallback(() => getChannels(), [])
  const { data: channels, error, loading, retry } = useFetch(fetcher, [])

  return (
    <div>
      <div className="page-header">
        <h1>Channels</h1>
        <p className="page-subtitle">
          YouTube channels tracked by the TrendCast ETL pipeline.
        </p>
      </div>

      {loading && <LoadingState label="Loading channels…" />}
      {!loading && error && <ErrorState error={error} onRetry={retry} />}
      {!loading && !error && channels?.length === 0 && (
        <EmptyState label="No channels found yet." />
      )}

      {!loading && !error && channels?.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Channel</th>
                <th>Subscribers</th>
                <th>Total views</th>
                <th>Videos</th>
                <th>Size tier</th>
              </tr>
            </thead>
            <tbody>
              {channels.map((channel) => (
                <tr
                  key={channel.channel_id}
                  className="clickable-row"
                  onClick={() => navigate(`/channels/${channel.channel_id}`)}
                >
                  <td className="cell-title">{channel.channel_title}</td>
                  <td>{formatCompactNumber(channel.subscriber_count)}</td>
                  <td>{formatCompactNumber(channel.total_views)}</td>
                  <td>{formatCompactNumber(channel.video_count)}</td>
                  <td>
                    <span className={`tier-badge tier-${slugify(channel.size_tier)}`}>
                      {channel.size_tier}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
