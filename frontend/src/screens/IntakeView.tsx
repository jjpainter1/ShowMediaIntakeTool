import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from 'react'
import {
  ApiError,
  executeIntake,
  copyProgressPercent,
  fetchShowConfig,
  formatIntakeError,
  openIntakeLog,
  scanIntake,
  type IntakeAction,
  type IntakeExecuteResult,
  type IntakeFilePlan,
  type IntakeScanResult,
  type ShowConfigData,
  type ShowSummary,
} from '../lib/api'
import { pickDeliverySource } from '../lib/folderPicker'
import { formatFileSize } from '../lib/format'
import { getIntakeSourcePath, saveIntakeSourcePath } from '../lib/intakeSourceStorage'

type IntakePhase = 'select' | 'scanning' | 'plan' | 'copying' | 'complete'

type PlanFilter = 'all' | 'copy' | 'warnings' | 'failures' | 'skip'

type SortKey = 'filename' | 'size' | 'resolution' | 'codec' | 'fps' | 'destination'

type IntakeViewProps = {
  show: ShowSummary
  onBusyChange: (busy: boolean) => void
  onComplete: () => void
}

const FILTER_CHIPS: { id: PlanFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'copy', label: 'Copy' },
  { id: 'warnings', label: 'Warnings' },
  { id: 'failures', label: 'Failures' },
  { id: 'skip', label: 'Skip' },
]

function actionBadge(action: IntakeAction): { label: string; className: string } {
  switch (action) {
    case 'COPY':
      return { label: '✓ COPY', className: 'intake-badge-copy' }
    case 'COPY_WITH_WARNING':
      return { label: '⚠ COPY', className: 'intake-badge-warn' }
    case 'ROUTE_TO_REVIEW':
      return { label: '✗ REVIEW', className: 'intake-badge-fail' }
    case 'SKIP_IDENTICAL':
      return { label: '• SKIP', className: 'intake-badge-skip' }
  }
}

function matchesFilter(plan: IntakeFilePlan, filter: PlanFilter): boolean {
  switch (filter) {
    case 'all':
      return true
    case 'copy':
      return plan.action === 'COPY' || plan.action === 'COPY_WITH_WARNING'
    case 'warnings':
      return plan.warnings.length > 0
    case 'failures':
      return plan.action === 'ROUTE_TO_REVIEW' || plan.failures.length > 0
    case 'skip':
      return plan.action === 'SKIP_IDENTICAL'
  }
}

function resolutionLabel(plan: IntakeFilePlan): string {
  const { specs } = plan
  if (!specs?.width || !specs.height) {
    return '—'
  }
  return `${specs.width}×${specs.height}`
}

function codecLabel(plan: IntakeFilePlan): string {
  const kind = plan.media_kind ?? plan.specs?.media_kind
  if (kind === 'image_sequence') {
    return 'sequence'
  }
  if (kind === 'image') {
    return 'still'
  }
  return plan.specs?.codec ?? '—'
}

function fpsLabel(plan: IntakeFilePlan): string {
  const kind = plan.media_kind ?? plan.specs?.media_kind
  if (kind === 'image' || kind === 'image_sequence') {
    return 'N/A'
  }
  const fps = plan.specs?.framerate
  if (fps == null) {
    return '—'
  }
  return fps.toFixed(3)
}

function sortPlans(plans: IntakeFilePlan[], key: SortKey, asc: boolean): IntakeFilePlan[] {
  const sorted = [...plans].sort((a, b) => {
    let cmp = 0
    switch (key) {
      case 'filename':
        cmp = a.filename.localeCompare(b.filename)
        break
      case 'size':
        cmp = a.size_bytes - b.size_bytes
        break
      case 'resolution': {
        const aw = a.specs?.width ?? 0
        const bw = b.specs?.width ?? 0
        cmp = aw - bw
        break
      }
      case 'codec':
        cmp = (a.specs?.codec ?? '').localeCompare(b.specs?.codec ?? '')
        break
      case 'fps':
        cmp = (a.specs?.framerate ?? 0) - (b.specs?.framerate ?? 0)
        break
      case 'destination':
        cmp = a.destination_label.localeCompare(b.destination_label)
        break
    }
    return asc ? cmp : -cmp
  })
  return sorted
}

function conflictLabel(plan: IntakeFilePlan): string | null {
  if (!plan.version_conflict || plan.parsed.kind !== 'full' || !plan.parsed.parsed) {
    return null
  }
  const { screen_prefix, slug } = plan.parsed.parsed
  const active = plan.version_conflict.existing_versions
    .map((v) => `v${String(v.version).padStart(2, '0')}`)
    .join(', ')
  const incoming = `v${String(plan.version_conflict.incoming_version).padStart(2, '0')}`
  return `${screen_prefix}_${slug}: ${active} (currently active) and ${incoming} (incoming)`
}

function planFileCount(plan: IntakeFilePlan): number {
  return plan.sequence_paths?.length ?? 1
}

export function IntakeView({ show, onBusyChange, onComplete }: IntakeViewProps) {
  const [phase, setPhase] = useState<IntakePhase>('select')
  const [sourcePath, setSourcePath] = useState(() => getIntakeSourcePath(show.path))
  const [scanProgress, setScanProgress] = useState({ current: 0, total: 0, filename: '' })
  const [scanResult, setScanResult] = useState<IntakeScanResult | null>(null)
  const [filter, setFilter] = useState<PlanFilter>('all')
  const [sortKey, setSortKey] = useState<SortKey>('filename')
  const [sortAsc, setSortAsc] = useState(true)
  const [copyProgress, setCopyProgress] = useState({
    current: 0,
    total: 0,
    percent: 0,
    filename: '',
    bytesCopied: 0,
    bytesTotal: 0,
    jobBytesCopied: 0,
    jobBytesTotal: 0,
  })
  const [copyLog, setCopyLog] = useState<{ text: string; tone: 'default' | 'ok' | 'fail' }[]>([])
  const [executeResult, setExecuteResult] = useState<IntakeExecuteResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showConfig, setShowConfig] = useState<ShowConfigData | null>(null)
  const [copiedOpen, setCopiedOpen] = useState(true)
  const [reviewOpen, setReviewOpen] = useState(true)
  const [skippedOpen, setSkippedOpen] = useState(false)
  const logEndRef = useRef<HTMLDivElement>(null)
  const copyDoneRef = useRef(0)

  const busy = phase === 'scanning' || phase === 'copying'
  const isFlatIntake = showConfig?.intake?.mode === 'flat'
  const canScan = Boolean(sourcePath.trim())

  useEffect(() => {
    let cancelled = false
    void fetchShowConfig(show.path)
      .then((config) => {
        if (!cancelled) {
          setShowConfig({
            ...config,
            intake: config.intake ?? { mode: 'routed' },
          })
        }
      })
      .catch(() => {
        if (!cancelled) {
          setShowConfig(null)
        }
      })
    return () => {
      cancelled = true
    }
  }, [show.path])

  useEffect(() => {
    setSourcePath(getIntakeSourcePath(show.path))
    setPhase('select')
    setScanResult(null)
    setExecuteResult(null)
    setCopyLog([])
    setError(null)
    setFilter('all')
  }, [show.path])

  useEffect(() => {
    saveIntakeSourcePath(show.path, sourcePath)
  }, [show.path, sourcePath])

  useEffect(() => {
    onBusyChange(busy)
  }, [busy, onBusyChange])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [copyLog])

  const filteredPlans = useMemo(() => {
    if (!scanResult) {
      return []
    }
    const filtered = scanResult.plans.filter((p) => matchesFilter(p, filter))
    return sortPlans(filtered, sortKey, sortAsc)
  }, [scanResult, filter, sortKey, sortAsc])

  const summary = useMemo(() => {
    const plans = scanResult?.plans ?? []
    const copyPlans = plans.filter(
      (p) => p.action === 'COPY' || p.action === 'COPY_WITH_WARNING',
    )
    const reviewPlans = plans.filter((p) => p.action === 'ROUTE_TO_REVIEW')
    const skipPlans = plans.filter((p) => p.action === 'SKIP_IDENTICAL')
    const copyBytes = copyPlans.reduce((sum, p) => sum + p.size_bytes, 0)
    const conflicts = plans.filter((p) => p.version_conflict)
    return { copyPlans, reviewPlans, skipPlans, copyBytes, conflicts }
  }, [scanResult])

  const resetToSelect = useCallback(() => {
    setPhase('select')
    setScanResult(null)
    setExecuteResult(null)
    setCopyLog([])
    setError(null)
    setFilter('all')
  }, [])

  async function handleBrowseSource() {
    setError(null)
    try {
      const selected = await pickDeliverySource('Select delivery source folder')
      if (selected) {
        setSourcePath(selected)
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError(
          'Folder picker unavailable. Restart the backend: .\\scripts\\start-backend.ps1',
        )
      } else {
        setError(err instanceof Error ? err.message : 'Could not open folder picker')
      }
    }
  }

  async function handleScan() {
    if (!canScan) {
      return
    }
    setError(null)
    setPhase('scanning')
    setScanProgress({ current: 0, total: 0, filename: '' })
    try {
      const result = await scanIntake(
        show.path,
        sourcePath.trim(),
        (progress) => {
          setScanProgress(progress)
        },
      )
      if (!result?.plans || !Array.isArray(result.plans)) {
        throw new Error('Scan returned an invalid response from the server')
      }
      setScanResult(result)
      setPhase('plan')
    } catch (err) {
      setError(formatIntakeError(err))
      setPhase('select')
    }
  }

  async function handleExecute() {
    if (!scanResult) {
      return
    }
    setError(null)
    setPhase('copying')
    setCopyLog([])
    const actionable = scanResult.plans.filter((p) => p.action !== 'SKIP_IDENTICAL')
    const totalFiles = actionable.reduce((sum, plan) => sum + planFileCount(plan), 0)
    const jobBytesTotal = actionable.reduce((sum, plan) => sum + plan.size_bytes, 0)
    copyDoneRef.current = 0
    setCopyProgress({
      current: 0,
      total: totalFiles,
      percent: 0,
      filename: '',
      bytesCopied: 0,
      bytesTotal: 0,
      jobBytesCopied: 0,
      jobBytesTotal: jobBytesTotal,
    })

    try {
      const result = await executeIntake(
        show.path,
        scanResult.source_path,
        scanResult.plans,
        scanResult.stale_folders,
        (progress) => {
          const total = progress.total || totalFiles
          if (progress.status === 'skipped') {
            return
          }

          const nextProgress = {
            current: progress.current,
            total,
            percent: copyProgressPercent(progress),
            filename: progress.filename,
            bytesCopied: progress.bytes_copied ?? 0,
            bytesTotal: progress.bytes_total ?? 0,
            jobBytesCopied: progress.job_bytes_copied ?? 0,
            jobBytesTotal: progress.job_bytes_total ?? jobBytesTotal,
          }

          if (progress.status === 'copying') {
            setCopyProgress(nextProgress)
            return
          }

          copyDoneRef.current = progress.current
          setCopyProgress(nextProgress)
          const line = `Copied ${progress.current} of ${total}: ${progress.filename} — ${
            progress.status === 'done' ? 'done' : 'FAILED'
          }`
          setCopyLog((lines) => [
            ...lines,
            {
              text: line,
              tone: progress.status === 'done' ? 'ok' : 'fail',
            },
          ])
        },
      )
      setExecuteResult(result)
      setPhase('complete')
      onComplete()
    } catch (err) {
      setError(formatIntakeError(err))
      setPhase('plan')
    }
  }

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc((v) => !v)
    } else {
      setSortKey(key)
      setSortAsc(true)
    }
  }

  function sortIndicator(key: SortKey): string {
    if (sortKey !== key) {
      return ''
    }
    return sortAsc ? ' ↑' : ' ↓'
  }

  if (phase === 'select') {
    return (
      <div className="intake">
        <header className="intake-header">
          <h1>Intake New Content Delivery</h1>
          <p className="intake-lead">
            {isFlatIntake
              ? 'Flat intake: scan a delivery folder. Valid files copy to Media\\_INCOMING with original names; strict spec failures go to _REVIEW.'
              : 'Select the source folder containing delivery files to scan and import into the show.'}
          </p>
        </header>

        {error && (
          <div className="banner banner-error" role="alert">
            {error}
          </div>
        )}

        <section className="intake-panel">
          <label className="intake-field-label" htmlFor="intake-source">
            Source Folder
          </label>
          <div className="intake-path-row">
            <input
              id="intake-source"
              className="intake-path-input"
              type="text"
              value={sourcePath}
              onChange={(e) => setSourcePath(e.target.value)}
              placeholder="D:\Deliveries\ShowName_2026-06-09"
            />
            <button type="button" className="btn-secondary" onClick={() => void handleBrowseSource()}>
              Browse…
            </button>
          </div>
          <button
            type="button"
            className="btn-primary intake-scan-btn"
            disabled={!canScan}
            onClick={() => void handleScan()}
          >
            🔍 Scan Folder
          </button>
        </section>
      </div>
    )
  }

  if (phase === 'scanning') {
    const { current, total, filename } = scanProgress
    const determinate = total > 0
    const percent = determinate ? Math.round((current / total) * 100) : 0

    return (
      <div className="intake intake-center">
        <h1 className="intake-progress-title">Scanning Files…</h1>
        <p className="intake-progress-label">
          {total > 0
            ? `Scanning ${current} of ${total} files…`
            : 'Walking source folder…'}
        </p>
        {filename && <p className="intake-progress-file">{filename}</p>}
        <div className="intake-progress-track">
          <div
            className={`intake-progress-fill${determinate ? '' : ' intake-progress-indeterminate'}`}
            style={determinate ? { width: `${percent}%` } : undefined}
          />
        </div>
      </div>
    )
  }

  if (phase === 'plan' && scanResult) {
    return (
      <div className="intake">
        <header className="intake-plan-header">
          <div>
            <h1>Intake Plan · {show.show_name}</h1>
            <p className="intake-meta">
              {scanResult.source_path} · {scanResult.plans.length} file
              {scanResult.plans.length === 1 ? '' : 's'}
              {scanResult.intake_mode === 'flat' ? ' · Flat → Media\\_INCOMING\\' : ''}
            </p>
          </div>
          <div className="intake-plan-actions">
            <button type="button" className="btn-secondary" onClick={resetToSelect}>
              ← Back
            </button>
            <button type="button" className="btn-primary" onClick={() => void handleExecute()}>
              Proceed with Copy →
            </button>
          </div>
        </header>

        {error && (
          <div className="banner banner-error" role="alert">
            {error}
          </div>
        )}

        <div className="intake-filter-row" role="group" aria-label="Plan filters">
          {FILTER_CHIPS.map((chip) => (
            <button
              key={chip.id}
              type="button"
              className={`intake-chip${filter === chip.id ? ' intake-chip-active' : ''}`}
              onClick={() => setFilter(chip.id)}
            >
              {chip.label}
            </button>
          ))}
        </div>

        <div className="intake-table-wrap">
          <table className="intake-table">
            <thead>
              <tr>
                <th>Action</th>
                <th>
                  <button type="button" className="intake-sort-btn" onClick={() => handleSort('filename')}>
                    Filename{sortIndicator('filename')}
                  </button>
                </th>
                <th>
                  <button type="button" className="intake-sort-btn" onClick={() => handleSort('size')}>
                    Size{sortIndicator('size')}
                  </button>
                </th>
                <th>
                  <button type="button" className="intake-sort-btn" onClick={() => handleSort('resolution')}>
                    Resolution{sortIndicator('resolution')}
                  </button>
                </th>
                <th>
                  <button type="button" className="intake-sort-btn" onClick={() => handleSort('codec')}>
                    Codec{sortIndicator('codec')}
                  </button>
                </th>
                <th>
                  <button type="button" className="intake-sort-btn" onClick={() => handleSort('fps')}>
                    FPS{sortIndicator('fps')}
                  </button>
                </th>
                <th>
                  <button type="button" className="intake-sort-btn" onClick={() => handleSort('destination')}>
                    Destination{sortIndicator('destination')}
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredPlans.map((plan) => {
                const badge = actionBadge(plan.action)
                return (
                  <PlanTableRows key={plan.source_path} plan={plan} badge={badge} />
                )
              })}
            </tbody>
          </table>
        </div>

        {summary.conflicts.length > 0 && (
          <section className="intake-warnings-block">
            <h2 className="intake-section-title">Version Conflicts Detected</h2>
            <ul className="intake-conflict-list">
              {summary.conflicts.map((plan) => {
                const label = conflictLabel(plan)
                return label ? <li key={plan.source_path}>{label}</li> : null
              })}
            </ul>
          </section>
        )}

        {scanResult.stale_folders.length > 0 && (
          <section className="intake-warnings-block">
            <h2 className="intake-section-title">Stale Folders</h2>
            <ul className="intake-conflict-list">
              {scanResult.stale_folders.map((sf) => (
                <li key={sf.name}>
                  <code>{sf.name}</code> — {sf.file_count} file{sf.file_count === 1 ? '' : 's'} not
                  listed in config
                </li>
              ))}
            </ul>
          </section>
        )}

        <footer className="intake-summary-bar">
          <span>
            {summary.copyPlans.length} file{summary.copyPlans.length === 1 ? '' : 's'} to copy (
            {formatFileSize(summary.copyBytes)})
          </span>
          <span className="intake-summary-sep">·</span>
          <span>
            {summary.reviewPlans.length} file{summary.reviewPlans.length === 1 ? '' : 's'} to _REVIEW
          </span>
          <span className="intake-summary-sep">·</span>
          <span>
            {summary.skipPlans.length} to skip
          </span>
        </footer>
      </div>
    )
  }

  if (phase === 'copying') {
    return (
      <div className="intake">
        <CopyLogPanel
          title="Copying Files…"
          percent={copyProgress.percent}
          current={copyProgress.current}
          total={copyProgress.total}
          activeFilename={copyProgress.filename}
          fileBytesCopied={copyProgress.bytesCopied}
          fileBytesTotal={copyProgress.bytesTotal}
          jobBytesCopied={copyProgress.jobBytesCopied}
          jobBytesTotal={copyProgress.jobBytesTotal}
          copyLog={copyLog}
          logEndRef={logEndRef}
          frozen={false}
        />
      </div>
    )
  }

  if (phase === 'complete' && executeResult && scanResult) {
    const { result } = executeResult
    const copiedPlans = scanResult.plans.filter((p) =>
      result.copied.some((path) => path.endsWith(p.filename)),
    )
    const reviewPlans = scanResult.plans.filter((p) =>
      result.routed_to_review.some((path) => path.endsWith(p.filename)),
    )
    const skippedPlans = scanResult.plans.filter((p) => p.action === 'SKIP_IDENTICAL')
    const copiedBytes = copiedPlans.reduce((sum, p) => sum + p.size_bytes, 0)

    return (
      <div className="intake">
        <CopyLogPanel
          title="Copying Files"
          percent={100}
          current={copyProgress.total}
          total={copyProgress.total}
          activeFilename=""
          fileBytesCopied={copyProgress.jobBytesCopied}
          fileBytesTotal={copyProgress.jobBytesTotal}
          jobBytesCopied={copyProgress.jobBytesCopied}
          jobBytesTotal={copyProgress.jobBytesTotal}
          copyLog={copyLog}
          logEndRef={logEndRef}
          frozen
        />

        <header className="intake-plan-header intake-complete-header">
          <h1>Intake Complete</h1>
          <button type="button" className="btn-primary" onClick={resetToSelect}>
            ↩ New Intake
          </button>
        </header>

        {result.copied.length > 0 && (
          <ResultsSection
            title={`✓ ${result.copied.length} files copied · ${formatFileSize(copiedBytes)} total`}
            tone="success"
            open={copiedOpen}
            onToggle={() => setCopiedOpen((v) => !v)}
          >
            <ul className="intake-results-list">
              {copiedPlans.map((plan) => (
                <li key={plan.source_path}>
                  <span>{plan.filename}</span>
                  {plan.infos?.map((info) => (
                    <p key={info} className="intake-sub-info">
                      INFO: {info}
                    </p>
                  ))}
                  {plan.warnings.map((w) => (
                    <p key={w} className="intake-sub-warn">
                      WARN: {w}
                    </p>
                  ))}
                </li>
              ))}
            </ul>
          </ResultsSection>
        )}

        {result.routed_to_review.length > 0 && (
          <ResultsSection
            title={`▲ ${result.routed_to_review.length} files routed to _REVIEW · require manual inspection`}
            tone="danger"
            open={reviewOpen}
            onToggle={() => setReviewOpen((v) => !v)}
          >
            <ul className="intake-results-list">
              {reviewPlans.map((plan) => (
                <li key={plan.source_path}>
                  <span>{plan.filename}</span>
                  {plan.failures.map((f) => (
                    <p key={f} className="intake-sub-fail">
                      FAIL: {f}
                    </p>
                  ))}
                </li>
              ))}
            </ul>
          </ResultsSection>
        )}

        {skippedPlans.length > 0 && (
          <ResultsSection
            title={`• ${skippedPlans.length} files skipped (already present)`}
            tone="muted"
            open={skippedOpen}
            onToggle={() => setSkippedOpen((v) => !v)}
          >
            <ul className="intake-results-list intake-results-muted">
              {skippedPlans.map((plan) => (
                <li key={plan.source_path}>{plan.filename}</li>
              ))}
            </ul>
          </ResultsSection>
        )}

        {result.copy_failures.length > 0 && (
          <section className="intake-warnings-block">
            <h2 className="intake-section-title">Copy Failures</h2>
            <ul className="intake-conflict-list">
              {result.copy_failures.map((item) => (
                <li key={item.source_path}>
                  {item.source_path} — {item.reason}
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="intake-log-block">
          <h2 className="intake-section-title">Intake Log</h2>
          <input
            className="intake-log-path"
            type="text"
            readOnly
            value={executeResult.intake_log_path}
          />
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void openIntakeLog(executeResult.intake_log_path)}
          >
            📄 Open Log in Text Editor
          </button>
        </section>
      </div>
    )
  }

  return (
    <div className="intake">
      <div className="banner banner-error" role="alert">
        Unexpected intake state. Return to folder selection and try again.
      </div>
      <button type="button" className="btn-secondary" onClick={resetToSelect}>
        ← Back to folder selection
      </button>
    </div>
  )
}

function CopyLogPanel({
  title,
  percent,
  current,
  total,
  activeFilename,
  fileBytesCopied,
  fileBytesTotal,
  jobBytesCopied,
  jobBytesTotal,
  copyLog,
  logEndRef,
  frozen,
}: {
  title: string
  percent: number
  current: number
  total: number
  activeFilename: string
  fileBytesCopied: number
  fileBytesTotal: number
  jobBytesCopied: number
  jobBytesTotal: number
  copyLog: { text: string; tone: 'default' | 'ok' | 'fail' }[]
  logEndRef: RefObject<HTMLDivElement | null>
  frozen: boolean
}) {
  const showIndeterminate =
    !frozen &&
    activeFilename &&
    percent === 0 &&
    jobBytesCopied === 0 &&
    fileBytesCopied === 0
  const progressLabel =
    jobBytesTotal > 0
      ? `${percent}% complete — ${formatFileSize(jobBytesCopied)} of ${formatFileSize(jobBytesTotal)}`
      : total > 0
        ? `${percent}% complete (${current} of ${total} files)`
        : `${percent}% complete`
  const filePercent =
    fileBytesTotal > 0 ? Math.min(100, Math.round((fileBytesCopied / fileBytesTotal) * 100)) : 0
  const showFileBar =
    !frozen && activeFilename && fileBytesTotal > 512 * 1024 && fileBytesCopied < fileBytesTotal

  return (
    <section className={`intake-copy-panel${frozen ? ' intake-copy-panel-frozen' : ''}`}>
      <h2 className="intake-progress-title">
        {title}
        {!frozen && <span className="intake-copy-active-dot" aria-hidden="true" />}
      </h2>
      <p className="intake-progress-label">{progressLabel}</p>
      {activeFilename && !frozen && (
        <p className="intake-progress-file intake-copy-active-file">{activeFilename}</p>
      )}
      {showFileBar && (
        <p className="intake-copy-file-bytes">
          Current file: {formatFileSize(fileBytesCopied)} of {formatFileSize(fileBytesTotal)} (
          {filePercent}%)
        </p>
      )}
      <div className="intake-progress-track">
        <div
          className={`intake-progress-fill${
            showIndeterminate ? ' intake-progress-indeterminate' : ''
          }`}
          style={showIndeterminate ? undefined : { width: `${percent}%` }}
        />
      </div>
      {showFileBar && (
        <div className="intake-progress-track intake-progress-track-sub">
          <div className="intake-progress-fill" style={{ width: `${filePercent}%` }} />
        </div>
      )}
      <div className="intake-copy-log">
        {copyLog.map((line, index) => (
          <p
            key={`${index}-${line.text.slice(0, 20)}`}
            className={`intake-copy-line intake-copy-${line.tone}`}
          >
            {line.text}
          </p>
        ))}
        {!frozen && <div ref={logEndRef} />}
      </div>
    </section>
  )
}

function PlanTableRows({
  plan,
  badge,
}: {
  plan: IntakeFilePlan
  badge: { label: string; className: string }
}) {
  return (
    <>
      <tr className="intake-row-main">
        <td>
          <span className={`intake-badge ${badge.className}`}>{badge.label}</span>
        </td>
        <td className="intake-filename">
          {plan.filename}
          {(plan.frame_count ?? 1) > 1 && (
            <span className="intake-frame-count"> ({plan.frame_count} frames)</span>
          )}
        </td>
        <td>{formatFileSize(plan.size_bytes)}</td>
        <td className={`intake-spec-${plan.spec_status.resolution}`}>
          {resolutionLabel(plan)}
        </td>
        <td className={`intake-spec-${plan.spec_status.codec}`}>
          {codecLabel(plan)}
        </td>
        <td className={`intake-spec-${plan.spec_status.fps}`}>{fpsLabel(plan)}</td>
        <td className="intake-dest">{plan.destination_label}</td>
      </tr>
      {plan.infos?.map((info) => (
        <tr key={`i-${info}`} className="intake-row-sub intake-row-info">
          <td />
          <td colSpan={6}>
            INFO: {info}
          </td>
        </tr>
      ))}
      {plan.warnings.map((w) => (
        <tr key={`w-${w}`} className="intake-row-sub intake-row-warn">
          <td />
          <td colSpan={6}>
            WARN: {w}
          </td>
        </tr>
      ))}
      {plan.failures.map((f) => (
        <tr key={`f-${f}`} className="intake-row-sub intake-row-fail">
          <td />
          <td colSpan={6}>
            FAIL: {f}
          </td>
        </tr>
      ))}
    </>
  )
}

function ResultsSection({
  title,
  tone,
  open,
  onToggle,
  children,
}: {
  title: string
  tone: 'success' | 'danger' | 'muted'
  open: boolean
  onToggle: () => void
  children: ReactNode
}) {
  return (
    <section className={`intake-results-section intake-results-${tone}`}>
      <button type="button" className="intake-results-toggle" onClick={onToggle}>
        <span>{open ? '▼' : '▶'}</span>
        <span>{title}</span>
      </button>
      {open && <div className="intake-results-body">{children}</div>}
    </section>
  )
}
