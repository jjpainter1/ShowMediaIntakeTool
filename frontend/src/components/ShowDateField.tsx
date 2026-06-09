import { useRef } from 'react'
import { isValidDate } from '../lib/configValidation'

type ShowDateFieldProps = {
  value: string
  onChange: (value: string) => void
  error?: string
  hint?: string
}

export function ShowDateField({
  value,
  onChange,
  error,
  hint = 'Use the calendar button if the picker does not open on click',
}: ShowDateFieldProps) {
  const dateInputRef = useRef<HTMLInputElement>(null)
  const dateValue = isValidDate(value) ? value : ''

  function openCalendar() {
    const input = dateInputRef.current
    if (!input) {
      return
    }
    input.focus()
    if (typeof input.showPicker === 'function') {
      try {
        input.showPicker()
      } catch {
        // showPicker can throw if not triggered by a user gesture in some hosts
      }
    }
  }

  return (
    <label className="field">
      <span>Show Date</span>
      <div className="config-date-row">
        <input
          ref={dateInputRef}
          type="date"
          className="config-date-input"
          value={dateValue}
          onChange={(event) => onChange(event.target.value)}
          onClick={() => openCalendar()}
        />
        <button
          type="button"
          className="btn-secondary config-date-btn"
          onClick={() => openCalendar()}
          aria-label="Open calendar"
          title="Pick a date"
        >
          📅
        </button>
      </div>
      {hint && <span className="field-hint">{hint}</span>}
      {error && <span className="config-field-error">{error}</span>}
    </label>
  )
}
