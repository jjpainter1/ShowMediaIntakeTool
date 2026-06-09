import { useState } from 'react'
import { Modal } from './Modal'

type MigrationModalProps = {
  showPath: string
  loading: boolean
  onMigrate: () => void
  onCancel: () => void
}

export function MigrationModal({ showPath, loading, onMigrate, onCancel }: MigrationModalProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <Modal title="Migrate v1 show config" onClose={onCancel}>
      <p className="modal-lead">
        This show was created in v1. To open it in v2, the config needs migration. A backup
        will be saved as <code>show_config.v1.bak.json</code>.
      </p>
      <p className="modal-path">{showPath}</p>
      {expanded && (
        <div className="modal-info">
          Migration adds <code>schema_version: 2</code> and <code>preset: &quot;pixera&quot;</code>.
          No existing fields are modified.
        </div>
      )}
      <div className="modal-actions">
        <button
          type="button"
          className="btn-secondary"
          onClick={() => setExpanded((value) => !value)}
        >
          View What Changes
        </button>
        <button type="button" className="btn-secondary" onClick={onCancel} disabled={loading}>
          Cancel
        </button>
        <button type="button" className="btn-primary" onClick={onMigrate} disabled={loading}>
          {loading ? 'Migrating…' : 'Migrate and Open'}
        </button>
      </div>
    </Modal>
  )
}
