export function LoadingState({ label = 'Loading…' }) {
  return <p className="state state-loading">{label}</p>
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="state state-error">
      <p>{error?.message || 'Something went wrong.'}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn-secondary">
          Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ label = 'Nothing to show yet.' }) {
  return <p className="state state-empty">{label}</p>
}
