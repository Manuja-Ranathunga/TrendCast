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
import { formatCompactNumber } from '../utils/format'

const emptyForm = { title: '', thumbnailUrl: '', scheduledUploadTime: '' }

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

  return (
    <div>
      <div className="page-header">
        <h1>Forecast</h1>
        <p className="page-subtitle">
          Project a 30-day view trajectory for a planned upload.
        </p>
      </div>

      <div className="notice-banner">
        <strong>Placeholder forecasts.</strong> The predictive model is not yet
        integrated — every submission currently returns the same mock curve
        from the backend, regardless of the inputs below.
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

        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? 'Forecasting…' : 'Generate forecast'}
        </button>
      </form>

      {loading && <LoadingState label="Generating forecast…" />}
      {!loading && error && <ErrorState error={error} onRetry={handleSubmit} />}

      {!loading && !error && curve && curve.length > 0 && (
        <div className="chart-panel">
          <ResponsiveContainer width="100%" height={360}>
            <LineChart data={curve} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="day"
                tick={{ fontSize: 12 }}
                label={{ value: 'Day', position: 'insideBottom', offset: -4 }}
              />
              <YAxis
                tick={{ fontSize: 12 }}
                tickFormatter={formatCompactNumber}
                width={56}
              />
              <Tooltip formatter={(value) => formatCompactNumber(value)} />
              <Line
                type="monotone"
                dataKey="views"
                stroke="var(--accent)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
