import { useCallback, useEffect, useMemo, useState } from 'react'
import { Banner } from '../components/Banner'
import { FilePanel } from '../components/FilePanel'
import { DeliveryHistoryModal } from '../components/DeliveryHistoryModal'
import { ScreenCard } from '../components/ScreenCard'
import { StatCard } from '../components/StatCard'
import {
  openPathInExplorer,
  patchDashboardView,
  type DashboardSnapshot,
  type DashboardViewMode,
  type ShowSummary,
} from '../lib/api'
import { formatVersionLine } from '../lib/format'

type DashboardViewProps = {
  show: ShowSummary
  snapshot: DashboardSnapshot | null
  loading: boolean
  error: string | null
  dashboardViewPref: DashboardViewMode | null
  onRefresh: () => void
  onNavigate: (view: 'intake' | 'spec') => void
  onDashboardViewChange: (view: DashboardViewMode) => void
}

function resolveViewMode(
  pref: DashboardViewMode | null,
  screenCount: number,
): DashboardViewMode {
  if (pref === 'cards' || pref === 'compact') {
    return pref
  }
  return screenCount > 12 ? 'compact' : 'cards'
}

function daysVariant(days: number | null): 'default' | 'warning' | 'danger' {
  if (days === null) {
    return 'default'
  }
  if (days <= 0) {
    return 'danger'
  }
  if (days <= 7) {
    return 'warning'
  }
  return 'default'
}

function daysLabel(days: number | null): string {
  if (days === null) {
    return '—'
  }
  if (days < 0) {
    const n = Math.abs(days)
    return `${n} day${n === 1 ? '' : 's'} ago`
  }
  if (days === 0) {
    return 'Today'
  }
  return `${days} day${days === 1 ? '' : 's'}`
}

export function DashboardView({
  show,
  snapshot,
  loading,
  error,
  dashboardViewPref,
  onRefresh,
  onNavigate,
  onDashboardViewChange,
}: DashboardViewProps) {
  const screens = useMemo(
    () => (snapshot ? Object.values(snapshot.screens) : []),
    [snapshot],
  )

  const viewMode = resolveViewMode(dashboardViewPref, screens.length)
  const [selectedScreenId, setSelectedScreenId] = useState<string | null>(null)
  const [multiBannerDismissed, setMultiBannerDismissed] = useState(false)
  const [staleBannerDismissed, setStaleBannerDismissed] = useState(false)
  const [multiExpanded, setMultiExpanded] = useState(false)
  const [staleExpanded, setStaleExpanded] = useState(false)
  const [deliveryModalOpen, setDeliveryModalOpen] = useState(false)

  useEffect(() => {
    setSelectedScreenId(null)
    setMultiBannerDismissed(false)
    setStaleBannerDismissed(false)
    setMultiExpanded(false)
    setStaleExpanded(false)
  }, [show.path])

  const selectedScreen = selectedScreenId
    ? snapshot?.screens[selectedScreenId] ?? null
    : null

  const totalFiles = useMemo(() => {
    if (!snapshot) {
      return 0
    }
    const screenTotal = screens.reduce((sum, s) => sum + s.file_count, 0)
    const specialTotal = Object.values(snapshot.special_folders).reduce(
      (sum, files) => sum + files.length,
      0,
    )
    return screenTotal + specialTotal
  }, [snapshot, screens])

  const totalSlugs = useMemo(() => {
    const slugs = new Set<string>()
    for (const screen of screens) {
      for (const pf of screen.parsed_files) {
        slugs.add(pf.slug)
      }
    }
    return slugs.size
  }, [screens])

  const handleViewChange = useCallback(
    async (mode: DashboardViewMode) => {
      onDashboardViewChange(mode)
      try {
        await patchDashboardView(show.path, mode)
      } catch {
        // Preference save failed; local UI still updates for this session.
      }
    },
    [onDashboardViewChange, show.path],
  )

  function openDeliveryHistory() {
    setDeliveryModalOpen(true)
  }

  const showDate = snapshot?.show_date ?? '—'

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div>
          <h1>{snapshot?.show_name ?? show.show_name}</h1>
          <p className="dashboard-meta">
            {showDate} · {show.path}
          </p>
        </div>
        <div className="dashboard-header-actions">
          <div className="view-toggle" role="group" aria-label="Screen layout">
            <button
              type="button"
              className={`view-toggle-btn${viewMode === 'cards' ? ' view-toggle-active' : ''}`}
              onClick={() => void handleViewChange('cards')}
            >
              ⊞ Cards
            </button>
            <button
              type="button"
              className={`view-toggle-btn${viewMode === 'compact' ? ' view-toggle-active' : ''}`}
              onClick={() => void handleViewChange('compact')}
            >
              ≣ Compact
            </button>
          </div>
          <button
            type="button"
            className="btn-ghost"
            onClick={() => void openPathInExplorer(show.path)}
            title={show.path}
          >
            📂 Show Folder
          </button>
          <button type="button" className="btn-ghost" onClick={onRefresh} disabled={loading}>
            {loading ? '↻ Refreshing…' : '↻ Refresh'}
          </button>
          <button type="button" className="btn-primary" onClick={() => onNavigate('intake')}>
            ↓ Intake Delivery
          </button>
          <button type="button" className="btn-secondary" disabled title="Coming in a later phase">
            ⎘ Generate Spec
          </button>
        </div>
      </header>

      {error && (
        <div className="banner banner-error" role="alert">
          {error}
        </div>
      )}

      {snapshot && !multiBannerDismissed && snapshot.multi_version_slugs.length > 0 && (
        <Banner
          actionLabel={multiExpanded ? 'Hide details' : 'View details'}
          onToggleExpand={() => setMultiExpanded((v) => !v)}
          expandedOpen={multiExpanded}
          onDismiss={() => setMultiBannerDismissed(true)}
          expanded={
            <ul className="banner-detail-list">
              {snapshot.multi_version_slugs.map((item) => (
                <li key={item.label}>
                  <code>{item.label}</code>
                  <span>{formatVersionLine(item.versions)}</span>
                </li>
              ))}
            </ul>
          }
        >
          {snapshot.multi_version_slugs.length} slug
          {snapshot.multi_version_slugs.length === 1 ? '' : 's'} have multiple versions present
        </Banner>
      )}

      {snapshot && !staleBannerDismissed && snapshot.stale_folders.length > 0 && (
        <Banner
          actionLabel={staleExpanded ? 'Hide' : 'Review'}
          onToggleExpand={() => setStaleExpanded((v) => !v)}
          expandedOpen={staleExpanded}
          onDismiss={() => setStaleBannerDismissed(true)}
          expanded={
            <ul className="banner-detail-list">
              {snapshot.stale_folders.map((folder) => (
                <li key={folder.name}>
                  <code>{folder.name}</code>
                  <span>
                    {folder.file_count} file{folder.file_count === 1 ? '' : 's'}
                  </span>
                </li>
              ))}
            </ul>
          }
        >
          {snapshot.stale_folders.length} unmanaged folder
          {snapshot.stale_folders.length === 1 ? '' : 's'} found in Media
        </Banner>
      )}

      {snapshot && screens.length === 0 && (
        <section className="dashboard-placeholder dashboard-empty-screens">
          <p>No screens configured yet.</p>
          <p className="dashboard-empty-screens-hint">
            Add screen IDs in Edit Config (or update <code>show_config.json</code>), then refresh
            the dashboard.
          </p>
        </section>
      )}

      {snapshot && screens.length > 0 && (
        <section className="screen-grid-section">
          {viewMode === 'compact' && (
            <div className="screen-compact-header" aria-hidden>
              <span>ID</span>
              <span>Name</span>
              <span>Resolution</span>
              <span>Files</span>
              <span>Slugs</span>
            </div>
          )}
          {viewMode === 'compact' ? (
            <div className="screen-list">
              {screens.map((screen) => (
                <div key={screen.screen_id} className="screen-list-item">
                  <ScreenCard
                    screen={screen}
                    compact
                    selected={selectedScreenId === screen.screen_id}
                    onSelect={() =>
                      setSelectedScreenId((id) =>
                        id === screen.screen_id ? null : screen.screen_id,
                      )
                    }
                  />
                  {selectedScreenId === screen.screen_id && (
                    <FilePanel showPath={show.path} screen={screen} inline />
                  )}
                </div>
              ))}
            </div>
          ) : (
            <>
              <div className="screen-grid">
                {screens.map((screen) => (
                  <ScreenCard
                    key={screen.screen_id}
                    screen={screen}
                    selected={selectedScreenId === screen.screen_id}
                    onSelect={() =>
                      setSelectedScreenId((id) =>
                        id === screen.screen_id ? null : screen.screen_id,
                      )
                    }
                  />
                ))}
              </div>
              {selectedScreen && <FilePanel showPath={show.path} screen={selectedScreen} />}
            </>
          )}
        </section>
      )}

      {snapshot && (
        <section className="stat-cards-row">
          <StatCard title="Total Content">
            <div className="stat-pair-row">
              <div className="stat-pair">
                <span className="stat-value">{totalFiles}</span>
                <span className="stat-label">total files</span>
              </div>
              <div className="stat-pair">
                <span className="stat-value">{totalSlugs}</span>
                <span className="stat-label">unique slugs</span>
              </div>
            </div>
          </StatCard>

          <StatCard title="Last Delivery">
            <p className="stat-delivery">
              {snapshot.last_delivery ? `✓ ${snapshot.last_delivery}` : 'No deliveries recorded'}
            </p>
            <button type="button" className="stat-link" onClick={() => void openDeliveryHistory()}>
              View delivery history
            </button>
          </StatCard>

          <StatCard
            title={
              snapshot.review_files.length > 0
                ? `▲ Review Queue (${snapshot.review_files.length})`
                : 'Review Queue'
            }
            variant={snapshot.review_files.length > 0 ? 'danger' : 'success'}
          >
            {snapshot.review_files.length > 0 ? (
              <>
                <ul className="review-list">
                  {snapshot.review_files.map((name) => (
                    <li key={name}>{name}</li>
                  ))}
                </ul>
                <button
                  type="button"
                  className="stat-link"
                  onClick={() =>
                    void openPathInExplorer(`${show.path.replace(/[/\\]$/, '')}/Media/_REVIEW`)
                  }
                >
                  📂 Open _REVIEW folder
                </button>
              </>
            ) : (
              <p className="stat-empty">✓ No files in review</p>
            )}
          </StatCard>

          <StatCard
            title="Days Until Show"
            variant={daysVariant(snapshot.days_until_show)}
          >
            <div className="stat-days-stack">
              <span className={`stat-value stat-days-${daysVariant(snapshot.days_until_show)}`}>
                {daysLabel(snapshot.days_until_show)}
              </span>
              {snapshot.show_date && (
                <span className="stat-label">Show date: {snapshot.show_date}</span>
              )}
            </div>
          </StatCard>
        </section>
      )}

      {!snapshot && !loading && !error && (
        <p className="dashboard-loading-hint">Loading dashboard…</p>
      )}

      {deliveryModalOpen && (
        <DeliveryHistoryModal
          showPath={show.path}
          onClose={() => setDeliveryModalOpen(false)}
        />
      )}
    </div>
  )
}
