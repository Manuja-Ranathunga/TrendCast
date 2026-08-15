import { useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { postForecast } from '../api/client'
import { ErrorState, LoadingState } from '../components/AsyncState'
import { ChartTooltip } from '../components/ChartTooltip'
import { formatCompactNumber } from '../utils/format'

const emptyForm = { title: '', thumbnailUrl: '', scheduledUploadTime: '' }
const CHECKPOINT_DAYS = [7, 15, 30]

export function Forecast() {
  const [form, setForm] = useState(emptyForm)
  const [curve, setCurve] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  function updateField(field) {
    return (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const result = await postForecast(form)
      setCurve(result)
    } catch (err) {
      setError(err)
      setCurve(null)
    } finally {
      setLoading(false)
    }
  }

  const checkpoints = CHECKPOINT_DAYS.map((day) => (curve || []).find((p) => p.day === day)).filter(Boolean)

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Forecast</h1>
        <p className="page-sub">Project a 30-day view trajectory for a planned upload.</p>
      </div>

      <div className="notice-banner">
        <span className="nb-dot" />
        <div>
          <strong>Placeholder forecasts.</strong> The predictive model is not yet
          integrated — every submission currently returns the same mock curve
          from the backend, regardless of the inputs below.
        </div>
      </div>

      <form className="forecast-form" onSubmit={handleSubmit}>
        <label className="field">
          <span>Video title</span>
          <input
            type="text"
            required
            value={form.title}
            onChange={updateField('title')}
            placeholder="e.g. My next big upload"
          />
        </label>

        <label className="field">
          <span>Thumbnail URL</span>
          <input
            type="text"
            required
            value={form.thumbnailUrl}
            onChange={updateField('thumbnailUrl')}
            placeholder="https://example.com/thumbnail.jpg"
          />
        </label>

        <label className="field">
          <span>Scheduled upload time</span>
          <input
            type="datetime-local"
            required
            value={form.scheduledUploadTime}
            onChange={updateField('scheduledUploadTime')}
          />
        </label>

        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Forecasting…' : 'Generate forecast'}
        </button>
      </form>

      {loading && <LoadingState label="Generating forecast…" />}
      {!loading && error && <ErrorState error={error} onRetry={handleSubmit} />}

      {!loading && !error && curve && curve.length > 0 && (
        <>
          {checkpoints.length > 0 && (
            <div className={`grid grid-${checkpoints.length} mt-16`}>
              {checkpoints.map((point) => (
                <div className="card stat-tile" key={point.day}>
                  <div className="st-top"><span className="st-label">Day {point.day}</span></div>
                  <div className="st-value mono">{formatCompactNumber(point.views)}</div>
                  <div className="st-sub">cumulative views (placeholder curve)</div>
                </div>
              ))}
            </div>
          )}

          <div className="card chart-panel mt-16">
            <div className="section-title">Projected view growth</div>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={curve} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--hairline)" />
                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 10.5, fill: 'var(--muted)' }}
                  axisLine={{ stroke: 'var(--hairline)' }}
                  tickLine={false}
                  label={{ value: 'Day', position: 'insideBottom', offset: -4, fontSize: 11, fill: 'var(--muted)' }}
                />
                <YAxis
                  tick={{ fontSize: 10.5, fill: 'var(--muted)' }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={formatCompactNumber}
                  width={44}
                />
                <Tooltip content={<ChartTooltip valueLabel="Views" formatter={formatCompactNumber} />} />
                <Line
                  type="monotone"
                  dataKey="views"
                  stroke="var(--series-views)"
                  strokeWidth={2.5}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  dot={false}
                  activeDot={{ r: 5, fill: 'var(--series-views)', stroke: 'var(--surface)', strokeWidth: 2 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
            <div className="chart-legend">
              <span className="legend-item">
                <span className="legend-swatch line" style={{ background: 'var(--series-views)' }} />
                Projected views
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
