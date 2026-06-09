import { useCallback, useEffect, useState } from 'react'
import {
  ApiError,
  createShow,
  fetchDashboard,
  fetchHealth,
  fetchRecentShows,
  formatDashboardError,
  loadShow,
  migrateShow,
  type DashboardSnapshot,
  type RecentShow,
  type DashboardViewMode,
  type ShowSummary,
} from './lib/api'
import { pickFolder } from './lib/folderPicker'
import { MigrationModal } from './components/MigrationModal'
import { NewShowModal } from './components/NewShowModal'
import { LaunchScreen } from './screens/LaunchScreen'
import { DashboardView } from './screens/DashboardView'
import { ConfigView } from './screens/ConfigView'
import { IntakeView } from './screens/IntakeView'
import { ShowLayout, type ShowView } from './screens/ShowLayout'
import './App.css'

type AppMode = 'launch' | 'show'

const DEFAULT_PARENT = 'D:\\Shows'

function App() {
  const [mode, setMode] = useState<AppMode>('launch')
  const [recentShows, setRecentShows] = useState<RecentShow[]>([])
  const [launchLoading, setLaunchLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [launchError, setLaunchError] = useState<string | null>(null)

  const [loadedShow, setLoadedShow] = useState<ShowSummary | null>(null)
  const [activeView, setActiveView] = useState<ShowView>('dashboard')
  const [dashboard, setDashboard] = useState<DashboardSnapshot | null>(null)
  const [dashboardLoading, setDashboardLoading] = useState(false)
  const [dashboardError, setDashboardError] = useState<string | null>(null)

  const [migrationPath, setMigrationPath] = useState<string | null>(null)
  const [showNewShowModal, setShowNewShowModal] = useState(false)
  const [dashboardViewPref, setDashboardViewPref] = useState<DashboardViewMode | null>(null)
  const [intakeBusy, setIntakeBusy] = useState(false)
  const [configDirty, setConfigDirty] = useState(false)

  const refreshRecent = useCallback(async () => {
    const shows = await fetchRecentShows()
    setRecentShows(shows)
  }, [])

  const refreshDashboard = useCallback(async (path: string) => {
    setDashboardLoading(true)
    setDashboardError(null)
    try {
      const data = await fetchDashboard(path)
      setDashboard(data)
    } catch (err) {
      setDashboardError(formatDashboardError(err))
    } finally {
      setDashboardLoading(false)
    }
  }, [])

  const openShow = useCallback(
    async (summary: ShowSummary, initialView: ShowView = 'dashboard') => {
      setLoadedShow(summary)
      setActiveView(initialView)
      setConfigDirty(false)
      setMode('show')
      setLaunchError(null)
      const shows = await fetchRecentShows()
      setRecentShows(shows)
      const recent = shows.find((s) => s.path === summary.path)
      const pref = recent?.dashboard_view
      setDashboardViewPref(
        pref === 'cards' || pref === 'compact' ? pref : null,
      )
      await refreshDashboard(summary.path)
    },
    [refreshDashboard],
  )

  const tryLoadShow = useCallback(
    async (path: string) => {
      setActionLoading(true)
      setLaunchError(null)
      try {
        const summary = await loadShow(path)
        await openShow(summary)
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          setMigrationPath(path)
        } else {
          setLaunchError(err instanceof Error ? err.message : 'Failed to load show')
        }
      } finally {
        setActionLoading(false)
      }
    },
    [openShow],
  )

  useEffect(() => {
    let cancelled = false

    async function init() {
      try {
        const [health, shows] = await Promise.all([fetchHealth(), fetchRecentShows()])
        if (!cancelled) {
          setRecentShows(shows)
          if (health.phase !== undefined && health.phase < 5) {
            setLaunchError(
              'Backend is out of date (phase ' +
                health.phase +
                '). Run .\\scripts\\start-backend.ps1 to restart on port 8000 with config editor support.',
            )
          } else {
            setLaunchError(null)
          }
        }
      } catch (err) {
        if (!cancelled) {
          setLaunchError(err instanceof Error ? err.message : 'Failed to reach backend')
        }
      } finally {
        if (!cancelled) {
          setLaunchLoading(false)
        }
      }
    }

    void init()
    return () => {
      cancelled = true
    }
  }, [])

  async function handleBrowse() {
    const selected = await pickFolder()
    if (!selected) {
      return
    }
    await tryLoadShow(selected)
  }

  async function handleMigrate() {
    if (!migrationPath) {
      return
    }
    setActionLoading(true)
    setLaunchError(null)
    try {
      await migrateShow(migrationPath)
      const summary = await loadShow(migrationPath)
      setMigrationPath(null)
      await openShow(summary)
    } catch (err) {
      setLaunchError(err instanceof Error ? err.message : 'Migration failed')
    } finally {
      setActionLoading(false)
    }
  }

  async function handleCreateShow(parentPath: string, showName: string, showDate: string) {
    setActionLoading(true)
    setLaunchError(null)
    try {
      const summary = await createShow(parentPath, showName, showDate)
      setShowNewShowModal(false)
      await openShow(summary, 'config')
    } catch (err) {
      setLaunchError(err instanceof Error ? err.message : 'Failed to create show')
    } finally {
      setActionLoading(false)
    }
  }

  function handleSwitchShow() {
    if (configDirty && !window.confirm('You have unsaved config changes. Discard them?')) {
      return
    }
    setMode('launch')
    setLoadedShow(null)
    setDashboard(null)
    setDashboardError(null)
    setActiveView('dashboard')
    setConfigDirty(false)
    void refreshRecent()
  }

  function handleNavigate(view: ShowView) {
    if (configDirty && activeView === 'config' && view !== 'config') {
      if (!window.confirm('You have unsaved config changes. Discard them?')) {
        return
      }
      setConfigDirty(false)
    }
    setActiveView(view)
  }

  if (mode === 'show' && loadedShow) {
    return (
      <>
        <ShowLayout
          show={loadedShow}
          activeView={activeView}
          navDisabled={intakeBusy}
          onNavigate={handleNavigate}
          onSwitchShow={handleSwitchShow}
        >
          {activeView === 'dashboard' && (
            <DashboardView
              show={loadedShow}
              snapshot={dashboard}
              loading={dashboardLoading}
              error={dashboardError}
              dashboardViewPref={dashboardViewPref}
              onRefresh={() => void refreshDashboard(loadedShow.path)}
              onNavigate={setActiveView}
              onDashboardViewChange={setDashboardViewPref}
            />
          )}
          {activeView === 'intake' && (
            <IntakeView
              show={loadedShow}
              onBusyChange={setIntakeBusy}
              onComplete={() => void refreshDashboard(loadedShow.path)}
            />
          )}
          {activeView === 'spec' && (
            <div className="dashboard-placeholder">
              <p>Generate Spec Doc ships in a later phase.</p>
            </div>
          )}
          {activeView === 'config' && (
            <ConfigView
              show={loadedShow}
              onDirtyChange={setConfigDirty}
              onSaved={(summary) => {
                setLoadedShow(summary)
                setConfigDirty(false)
                void refreshDashboard(summary.path)
              }}
            />
          )}
        </ShowLayout>
      </>
    )
  }

  return (
    <>
      <LaunchScreen
        recentShows={recentShows}
        loading={launchLoading || actionLoading}
        error={launchError}
        onSelectShow={(path) => void tryLoadShow(path)}
        onBrowse={() => void handleBrowse()}
        onNewShow={() => setShowNewShowModal(true)}
      />
      {migrationPath && (
        <MigrationModal
          showPath={migrationPath}
          loading={actionLoading}
          onMigrate={() => void handleMigrate()}
          onCancel={() => setMigrationPath(null)}
        />
      )}
      {showNewShowModal && (
        <NewShowModal
          defaultParentPath={DEFAULT_PARENT}
          loading={actionLoading}
          onCreate={(parentPath, showName, showDate) =>
            void handleCreateShow(parentPath, showName, showDate)
          }
          onClose={() => setShowNewShowModal(false)}
        />
      )}
    </>
  )
}

export default App
