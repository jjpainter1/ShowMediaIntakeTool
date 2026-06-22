import { useCallback, useState } from 'react'
import {
  formatSpecError,
  generateSpec,
  openSpecFile,
  type ShowSummary,
} from '../lib/api'

type SpecViewProps = {
  show: ShowSummary
}

type SpecPhase = 'idle' | 'generating' | 'success' | 'error'

export function SpecView({ show }: SpecViewProps) {
  const [phase, setPhase] = useState<SpecPhase>('idle')
  const [outputPath, setOutputPath] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [opening, setOpening] = useState(false)

  const handleGenerate = useCallback(async () => {
    setPhase('generating')
    setError(null)
    setOutputPath(null)
    try {
      const result = await generateSpec(show.path)
      setOutputPath(result.output_path)
      setPhase('success')
    } catch (err) {
      setError(formatSpecError(err))
      setPhase('error')
    }
  }, [show.path])

  const handleOpenFile = useCallback(async () => {
    if (!outputPath) {
      return
    }
    setOpening(true)
    setError(null)
    try {
      await openSpecFile(outputPath)
    } catch (err) {
      setError(formatSpecError(err))
    } finally {
      setOpening(false)
    }
  }, [outputPath])

  function handleReset() {
    setPhase('idle')
    setOutputPath(null)
    setError(null)
  }

  const generating = phase === 'generating'

  return (
    <div className="spec-view">
      <header className="spec-header">
        <h1>Generate Spec Document</h1>
        <p className="spec-lead">
          Generate a delivery specification document for vendors and content creators based on
          the current show configuration saved on disk.
        </p>
      </header>

      {phase === 'success' && outputPath && (
        <section className="spec-result spec-result-success" role="status">
          <p className="spec-result-title">✓ Spec document generated successfully</p>
          <label className="spec-path-label" htmlFor="spec-output-path">
            Output file
          </label>
          <input
            id="spec-output-path"
            className="spec-path-input"
            type="text"
            readOnly
            value={outputPath}
          />
          <div className="spec-actions">
            <button
              type="button"
              className="btn-primary"
              disabled={opening}
              onClick={() => void handleOpenFile()}
            >
              {opening ? 'Opening…' : '📂 Open File'}
            </button>
            <button type="button" className="btn-secondary" onClick={handleReset}>
              Generate Another
            </button>
          </div>
        </section>
      )}

      {phase === 'error' && error && (
        <section className="spec-result spec-result-error" role="alert">
          <p className="spec-result-title">Spec generation failed</p>
          <p className="spec-error-message">{error}</p>
        </section>
      )}

      {(phase === 'idle' || phase === 'error' || phase === 'generating') && (
        <section className="spec-panel">
          <p className="spec-panel-hint">
            Output: <code>{show.show_name}_DeliverySpec.docx</code> in the show folder. Existing
            files with the same name are overwritten.
          </p>
          <button
            type="button"
            className="btn-primary spec-generate-btn"
            disabled={generating}
            onClick={() => void handleGenerate()}
          >
            {generating ? 'Generating…' : '⎘ Generate Document'}
          </button>
        </section>
      )}

      {phase === 'success' && error && (
        <div className="banner banner-error" role="alert">
          {error}
        </div>
      )}
    </div>
  )
}
