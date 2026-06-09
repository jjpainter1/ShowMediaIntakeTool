import type { ReactNode } from 'react'
import { openPathInExplorer, type ShowSummary } from '../lib/api'

export type ShowView = 'dashboard' | 'intake' | 'spec' | 'config'

type ShowLayoutProps = {
  show: ShowSummary
  activeView: ShowView
  navDisabled?: boolean
  onNavigate: (view: ShowView) => void
  onSwitchShow: () => void
  children: ReactNode
}

const NAV_ITEMS: { id: ShowView; label: string; disabled?: boolean }[] = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'intake', label: 'Intake' },
  { id: 'spec', label: 'Spec Doc', disabled: true },
  { id: 'config', label: 'Config' },
]

export function ShowLayout({
  show,
  activeView,
  navDisabled = false,
  onNavigate,
  onSwitchShow,
  children,
}: ShowLayoutProps) {
  return (
    <div className="show-layout">
      <aside className="sidebar">
        <div className="show-card">
          <strong className="show-card-name">{show.show_name}</strong>
          <span className="show-card-meta">schema v{show.schema_version ?? 1}</span>
          <button
            type="button"
            className="show-card-path-btn"
            title={show.path}
            onClick={() => void openPathInExplorer(show.path)}
          >
            📂 Open folder
          </button>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-btn${activeView === item.id ? ' nav-btn-active' : ''}`}
              onClick={() => onNavigate(item.id)}
              disabled={item.disabled || navDisabled}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <button
          type="button"
          className="nav-btn nav-btn-switch"
          onClick={onSwitchShow}
          disabled={navDisabled}
        >
          ⇄ Switch Show
        </button>
      </aside>

      <main className="content-area">{children}</main>
    </div>
  )
}
