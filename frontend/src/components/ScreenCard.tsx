import type { ScreenSnapshot } from '../lib/api'

type ScreenCardProps = {
  screen: ScreenSnapshot
  selected: boolean
  compact?: boolean
  onSelect: () => void
}

export function ScreenCard({ screen, selected, compact = false, onSelect }: ScreenCardProps) {
  if (compact) {
    return (
      <button
        type="button"
        className={`screen-row${selected ? ' screen-row-selected' : ''}`}
        onClick={onSelect}
      >
        <span className="screen-id">{screen.screen_id}</span>
        <span className="screen-name">{screen.screen_name}</span>
        <span className="screen-resolution">{screen.resolution ?? '—'}</span>
        <span className="screen-stat">{screen.file_count}</span>
        <span className="screen-stat">{screen.slug_count}</span>
      </button>
    )
  }

  return (
    <button
      type="button"
      className={`screen-card${selected ? ' screen-card-selected' : ''}`}
      onClick={onSelect}
    >
      <span className="screen-id">{screen.screen_id}</span>
      <span className="screen-name">{screen.screen_name}</span>
      <span className="screen-resolution">{screen.resolution ?? '—'}</span>
      <div className="screen-card-stats">
        <div>
          <strong>{screen.file_count}</strong>
          <span>files</span>
        </div>
        <div>
          <strong>{screen.slug_count}</strong>
          <span>slugs</span>
        </div>
      </div>
      <span className="screen-card-hint">{selected ? '▲ Hide files' : '▼ View files'}</span>
    </button>
  )
}
