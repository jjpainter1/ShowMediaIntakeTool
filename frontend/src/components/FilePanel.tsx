import { useEffect, useMemo, useState } from 'react'
import {
  fetchScreenFiles,
  formatDashboardError,
  openPathInExplorer,
  type ScreenFileDetail,
  type ScreenSnapshot,
} from '../lib/api'
import { formatFileSize } from '../lib/format'

type SortKey = 'filename' | 'size_bytes' | 'resolution' | 'codec' | 'fps' | 'location'
type SortDir = 'asc' | 'desc'

type FilePanelProps = {
  showPath: string
  screen: ScreenSnapshot
  inline?: boolean
}

function resolutionLabel(file: ScreenFileDetail): string {
  const { width, height } = file.specs
  if (!width || !height) {
    return '—'
  }
  return `${width}×${height}`
}

function fpsLabel(file: ScreenFileDetail): string {
  const fps = file.specs.framerate
  if (fps == null) {
    return '—'
  }
  return fps.toFixed(3)
}

function rowTone(file: ScreenFileDetail): string {
  if (file.failures.length > 0) {
    return 'file-row-fail'
  }
  if (file.warnings.length > 0) {
    return 'file-row-warn'
  }
  return ''
}

export function FilePanel({ showPath, screen, inline = false }: FilePanelProps) {
  const [files, setFiles] = useState<ScreenFileDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('filename')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    void fetchScreenFiles(showPath, screen.screen_id)
      .then((data) => {
        if (!cancelled) {
          setFiles(data.files)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(formatDashboardError(err))
          setFiles([])
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
  }, [showPath, screen.screen_id])

  const sortedFiles = useMemo(() => {
    const next = [...files]
    next.sort((a, b) => {
      let cmp = 0
      switch (sortKey) {
        case 'filename':
          cmp = a.filename.localeCompare(b.filename, undefined, { sensitivity: 'base' })
          break
        case 'size_bytes':
          cmp = a.size_bytes - b.size_bytes
          break
        case 'resolution': {
          const aw = a.specs.width ?? 0
          const bw = b.specs.width ?? 0
          cmp = aw - bw
          break
        }
        case 'codec':
          cmp = (a.specs.codec ?? '').localeCompare(b.specs.codec ?? '')
          break
        case 'fps':
          cmp = (a.specs.framerate ?? 0) - (b.specs.framerate ?? 0)
          break
        case 'location':
          cmp = a.location.localeCompare(b.location)
          break
      }
      return sortDir === 'asc' ? cmp : -cmp
    })
    return next
  }, [files, sortKey, sortDir])

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  function sortIndicator(key: SortKey) {
    if (sortKey !== key) {
      return ''
    }
    return sortDir === 'asc' ? ' ▲' : ' ▼'
  }

  return (
    <div className={`file-panel${inline ? ' file-panel-inline' : ''}`}>
      {!inline && (
        <header className="file-panel-header">
          <span className="screen-id">{screen.screen_id}</span>
          <strong>{screen.screen_name}</strong>
          <span className="screen-resolution">{screen.resolution ?? '—'}</span>
          <span className="file-panel-count">{screen.file_count} files</span>
        </header>
      )}
      {loading && <p className="file-panel-empty">Reading file specs…</p>}
      {!loading && error && <p className="file-panel-empty file-panel-error">{error}</p>}
      {!loading && !error && sortedFiles.length === 0 && (
        <p className="file-panel-empty">No files in this screen folder.</p>
      )}
      {!loading && !error && sortedFiles.length > 0 && (
        <div className="file-table-wrap">
          <table className="file-table file-table-rich">
            <thead>
              <tr>
                <th>
                  <button type="button" className="file-sort-btn" onClick={() => toggleSort('filename')}>
                    Filename{sortIndicator('filename')}
                  </button>
                </th>
                <th className="file-col-size">
                  <button type="button" className="file-sort-btn" onClick={() => toggleSort('size_bytes')}>
                    Size{sortIndicator('size_bytes')}
                  </button>
                </th>
                <th>
                  <button type="button" className="file-sort-btn" onClick={() => toggleSort('resolution')}>
                    Resolution{sortIndicator('resolution')}
                  </button>
                </th>
                <th>
                  <button type="button" className="file-sort-btn" onClick={() => toggleSort('codec')}>
                    Codec{sortIndicator('codec')}
                  </button>
                </th>
                <th>
                  <button type="button" className="file-sort-btn" onClick={() => toggleSort('fps')}>
                    FPS{sortIndicator('fps')}
                  </button>
                </th>
                <th>
                  <button type="button" className="file-sort-btn" onClick={() => toggleSort('location')}>
                    Location{sortIndicator('location')}
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedFiles.map((file) => (
                <tr key={file.filename} className={rowTone(file)}>
                  <td className="file-name">{file.filename}</td>
                  <td className="file-size">{formatFileSize(file.size_bytes)}</td>
                  <td className={`intake-spec-${file.spec_status.resolution}`}>
                    {resolutionLabel(file)}
                  </td>
                  <td className={`intake-spec-${file.spec_status.codec}`}>
                    {file.specs.codec ?? '—'}
                  </td>
                  <td className={`intake-spec-${file.spec_status.fps}`}>{fpsLabel(file)}</td>
                  <td className="file-location-cell">
                    <div className="file-location-row">
                      <span className="file-location">{file.location}</span>
                      <button
                        type="button"
                        className="file-open-btn"
                        title="Show in File Explorer"
                        aria-label={`Show ${file.filename} in File Explorer`}
                        onClick={() => void openPathInExplorer(file.file_path)}
                      >
                        📂
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
