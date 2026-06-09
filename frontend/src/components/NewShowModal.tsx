import { useMemo, useState } from 'react'
import { pickFolder } from '../lib/folderPicker'
import { isFilenameSafe, isValidDate } from '../lib/configValidation'
import { buildShowFolderName, todayIsoDate } from '../lib/showFolder'
import { ShowDateField } from './ShowDateField'
import { Modal } from './Modal'

type NewShowModalProps = {
  defaultParentPath: string
  loading: boolean
  onCreate: (parentPath: string, showName: string, showDate: string) => void
  onClose: () => void
}

export function NewShowModal({
  defaultParentPath,
  loading,
  onCreate,
  onClose,
}: NewShowModalProps) {
  const [parentPath, setParentPath] = useState(defaultParentPath)
  const [showName, setShowName] = useState('')
  const [showDate, setShowDate] = useState(todayIsoDate)
  const [nameError, setNameError] = useState<string | null>(null)
  const [dateError, setDateError] = useState<string | null>(null)

  const folderPreview = useMemo(() => {
    const trimmed = showName.trim()
    if (!trimmed || !isValidDate(showDate)) {
      return null
    }
    return buildShowFolderName(trimmed, showDate)
  }, [showName, showDate])

  async function browseParent() {
    const selected = await pickFolder('Select parent folder for new show')
    if (selected) {
      setParentPath(selected)
    }
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmedName = showName.trim()
    let valid = true

    if (!trimmedName) {
      setNameError('Show name is required')
      valid = false
    } else if (!isFilenameSafe(trimmedName)) {
      setNameError('Only letters, digits, hyphens, and underscores')
      valid = false
    } else {
      setNameError(null)
    }

    if (!isValidDate(showDate)) {
      setDateError('Pick a valid show date')
      valid = false
    } else {
      setDateError(null)
    }

    if (!valid || !parentPath.trim()) {
      return
    }

    onCreate(parentPath.trim(), trimmedName, showDate)
  }

  return (
    <Modal title="Create New Show" onClose={onClose}>
      <form className="modal-form" onSubmit={handleSubmit}>
        <label className="field">
          <span>Parent folder</span>
          <div className="field-row">
            <input
              type="text"
              value={parentPath}
              onChange={(event) => setParentPath(event.target.value)}
              placeholder="D:\Shows"
            />
            <button type="button" className="btn-secondary" onClick={() => void browseParent()}>
              Browse
            </button>
          </div>
        </label>
        <label className="field">
          <span>Show Name</span>
          <input
            type="text"
            value={showName}
            onChange={(event) => {
              setShowName(event.target.value)
              setNameError(null)
            }}
            placeholder="Gala"
            autoFocus
          />
          {nameError && <span className="config-field-error">{nameError}</span>}
        </label>
        <ShowDateField
          value={showDate}
          onChange={(value) => {
            setShowDate(value)
            setDateError(null)
          }}
          error={dateError ?? undefined}
        />
        {folderPreview && (
          <p className="modal-info">
            Folder will be created as: <code>{folderPreview}</code>
          </p>
        )}
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button
            type="submit"
            className="btn-primary"
            disabled={loading || !showName.trim() || !isValidDate(showDate)}
          >
            {loading ? 'Creating…' : 'Create'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
