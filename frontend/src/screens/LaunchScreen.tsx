import type { RecentShow } from '../lib/api'
import { formatRelativeTime } from '../lib/time'

type LaunchScreenProps = {
  recentShows: RecentShow[]
  loading: boolean
  error: string | null
  onSelectShow: (path: string) => void
  onBrowse: () => void
  onNewShow: () => void
}

export function LaunchScreen({
  recentShows,
  loading,
  error,
  onSelectShow,
  onBrowse,
  onNewShow,
}: LaunchScreenProps) {
  return (
    <div className="launch-screen">
      <div className="launch-inner">
        <header className="launch-header">
          <h1>Show Media Intake Tool</h1>
          <p className="launch-subtitle">v2.0 · by JJ Painter</p>
        </header>

        {error && (
          <div className="banner banner-error" role="alert">
            {error}
          </div>
        )}

        <section className="recent-panel">
          <h2 className="section-label">RECENT SHOWS</h2>
          {loading ? (
            <p className="empty-state">Loading recent shows…</p>
          ) : recentShows.length === 0 ? (
            <p className="empty-state">No recent shows. Browse for one or create new.</p>
          ) : (
            <ul className="recent-rows">
              {recentShows.map((show) => (
                <li key={show.path}>
                  <button
                    type="button"
                    className="recent-row"
                    onClick={() => onSelectShow(show.path)}
                  >
                    <div className="recent-row-main">
                      <strong>{show.show_name}</strong>
                      <span className="recent-path">{show.path}</span>
                    </div>
                    <span className="recent-time">{formatRelativeTime(show.last_used)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="launch-actions">
          <button type="button" className="btn-primary btn-large" onClick={onBrowse}>
            Browse for Show Folder
          </button>
          <button type="button" className="btn-secondary" onClick={onNewShow}>
            + New Show
          </button>
        </div>
      </div>
    </div>
  )
}
