export function LoadingState({ label = 'Loading…' }) {
  return (
    <div className="state-loading">
      <div className="spinner" />
      <div className="state-label">{label}</div>
    </div>
  )
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="empty-state state-error">
      <div className="es-icon">⚠</div>
      <h3>Something went wrong</h3>
      <p>{error?.message || 'Please try again.'}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn btn-ghost btn-sm">
          Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ label = 'Nothing to show yet.' }) {
  return (
    <div className="empty-state">
      <div className="es-icon">📭</div>
      <p>{label}</p>
    </div>
  )
}
