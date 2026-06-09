import { useCallback, useEffect, useState } from 'react'
import {
  fetchDeliveryHistory,
  fetchIntakeLogContent,
  openIntakeLog,
  type DeliveryHistoryEntry,
} from '../lib/api'
import { Modal } from './Modal'

type DeliveryHistoryModalProps = {
  showPath: string
  onClose: () => void
}

function sourceLabel(sourcePath: string): string {
  const parts = sourcePath.replace(/\\/g, '/').split('/')
  return parts[parts.length - 1] || sourcePath
}

function intakeLogName(logPath: string): string {
  const parts = logPath.replace(/\\/g, '/').split('/')
  return parts[parts.length - 1] || logPath
}

type EntryCardProps = {
  entry: DeliveryHistoryEntry
  expanded: boolean
  logContent: string | null
  logLoading: boolean
  logError: string | null
  onToggleLog: () => void
}

function EntryCard({
  entry,
  expanded,
  logContent,
  logLoading,
  logError,
  onToggleLog,
}: EntryCardProps) {
  const hasIntakeLog = Boolean(entry.intake_log_path)

  return (
    <article className="delivery-history-card">
      <div className="delivery-history-card-head">
        <time className="delivery-history-time" dateTime={entry.timestamp}>
          {entry.timestamp}
        </time>
        <div className="delivery-history-stats">
          {entry.copied > 0 && (
            <span className="delivery-stat delivery-stat-copied">{entry.copied} copied</span>
          )}
          {entry.review > 0 && (
            <span className="delivery-stat delivery-stat-review">{entry.review} review</span>
          )}
          {entry.skip > 0 && (
            <span className="delivery-stat delivery-stat-skip">{entry.skip} skip</span>
          )}
          {entry.copied === 0 && entry.review === 0 && entry.skip === 0 && (
            <span className="delivery-stat delivery-stat-muted">No file changes</span>
          )}
        </div>
      </div>

      <p className="delivery-history-source" title={entry.source_path}>
        From <span className="delivery-history-source-name">{sourceLabel(entry.source_path)}</span>
      </p>
      <p className="delivery-history-source-path" title={entry.source_path}>
        {entry.source_path}
      </p>

      {entry.notes && <p className="delivery-history-notes">{entry.notes}</p>}

      {hasIntakeLog ? (
        <div className="delivery-history-actions">
          <button type="button" className="stat-link delivery-history-log-toggle" onClick={onToggleLog}>
            {expanded ? 'Hide intake log' : `View intake log (${intakeLogName(entry.intake_log_path!)})`}
          </button>
          <button
            type="button"
            className="btn-ghost delivery-history-open-editor"
            onClick={() => void openIntakeLog(entry.intake_log_path!)}
          >
            Open in editor
          </button>
        </div>
      ) : (
        <p className="delivery-history-missing-log">No intake log linked for this delivery.</p>
      )}

      {expanded && hasIntakeLog && (
        <div className="delivery-history-log-panel">
          {logLoading ? (
            <p className="modal-lead">Loading intake log…</p>
          ) : logError ? (
            <p className="delivery-history-log-error">{logError}</p>
          ) : (
            <pre className="delivery-history-log-content">{logContent}</pre>
          )}
        </div>
      )}
    </article>
  )
}

export function DeliveryHistoryModal({ showPath, onClose }: DeliveryHistoryModalProps) {
  const [entries, setEntries] = useState<DeliveryHistoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedKey, setExpandedKey] = useState<string | null>(null)
  const [logCache, setLogCache] = useState<Record<string, string>>({})
  const [logLoadingKey, setLogLoadingKey] = useState<string | null>(null)
  const [logError, setLogError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void fetchDeliveryHistory(showPath)
      .then((data) => {
        if (!cancelled) {
          setEntries([...data.entries].reverse())
        }
      })
      .catch(() => {
        if (!cancelled) {
          setEntries([])
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [showPath])

  const entryKey = useCallback((entry: DeliveryHistoryEntry, index: number) => {
    return `${entry.timestamp}-${entry.source_path}-${index}`
  }, [])

  const toggleLog = useCallback(
    async (entry: DeliveryHistoryEntry, key: string) => {
      if (!entry.intake_log_path) {
        return
      }

      if (expandedKey === key) {
        setExpandedKey(null)
        setLogError(null)
        return
      }

      setExpandedKey(key)
      setLogError(null)

      if (logCache[entry.intake_log_path]) {
        return
      }

      setLogLoadingKey(key)
      try {
        const data = await fetchIntakeLogContent(showPath, entry.intake_log_path)
        setLogCache((prev) => ({ ...prev, [entry.intake_log_path!]: data.content }))
      } catch {
        setLogError('Could not load intake log.')
      } finally {
        setLogLoadingKey(null)
      }
    },
    [expandedKey, logCache, showPath],
  )

  return (
    <Modal title="Delivery History" onClose={onClose}>
      {loading ? (
        <p className="modal-lead">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="modal-lead">No deliveries recorded yet. Run intake to add entries.</p>
      ) : (
        <div className="delivery-history-list">
          {entries.map((entry, index) => {
            const key = entryKey(entry, index)
            return (
              <EntryCard
                key={key}
                entry={entry}
                expanded={expandedKey === key}
                logContent={
                  entry.intake_log_path ? logCache[entry.intake_log_path] ?? null : null
                }
                logLoading={logLoadingKey === key}
                logError={expandedKey === key ? logError : null}
                onToggleLog={() => void toggleLog(entry, key)}
              />
            )
          })}
        </div>
      )}
    </Modal>
  )
}
