// Recharts custom tooltip content, styled to match the reference app's
// .chart-tooltip (dark chip, ink/page swap, rounded) — see index.css
// .chart-tooltip-content for why this doesn't reuse that class name as-is.
export function ChartTooltip({ active, payload, label, valueLabel = 'Views', formatter }) {
  if (!active || !payload || !payload.length) return null
  const value = payload[0]?.value
  return (
    <div className="chart-tooltip-content">
      <div className="ctt-label">{label}</div>
      <div>
        {valueLabel}: {formatter ? formatter(value) : value}
      </div>
    </div>
  )
}
