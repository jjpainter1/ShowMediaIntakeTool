import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  applyPreset,
  fetchCodecIdentifiers,
  fetchPresets,
  fetchShowConfig,
  formatConfigError,
  importPresetFile,
  openShowConfig,
  pickFileFromServer,
  saveCustomPreset,
  saveShowConfig,
  type PresetData,
  type ScreenExpectedSpecs,
  type ShowConfigData,
  type ShowSummary,
} from '../lib/api'
import {
  ALL_FILENAME_TOKENS,
  buildConfigPayload,
  buildExampleFilename,
  conventionEnabled,
  conventionUsesShowToken,
  DEFAULT_SCREEN_NOTES,
  FILENAME_TOKEN_META,
  DEFAULT_FILENAME_TOKENS,
  DEFAULT_IMAGE_EXTENSIONS,
  expectedMediaFrom,
  type FilenameTokenId,
  isPerScreenOutput,
  isSpecNa,
  outputSpecsMode,
  screenSpecsFromShow,
  validateAll,
  type ConfigTab,
  type FieldErrors,
  type StrictnessLevel,
} from '../lib/configValidation'
import { ShowDateField } from '../components/ShowDateField'

type ConfigViewProps = {
  show: ShowSummary
  onSaved: (summary: ShowSummary) => void
  onDirtyChange?: (dirty: boolean) => void
}

type SpecField = keyof ShowConfigData['expected_specs']

const TABS: { id: ConfigTab; label: string }[] = [
  { id: 'info', label: 'Show Info' },
  { id: 'specs', label: 'Expected Specs' },
  { id: 'screens', label: 'Screens' },
  { id: 'validation', label: 'Validation' },
]

const FRAMERATE_OPTIONS = ['23.976', '24', '25', '29.97', '30', '50', '59.94', '60']
const COLOR_SPACE_OPTIONS = ['bt709', 'bt2020', 'smpte170m', 'gbr']
const COLOR_RANGE_OPTIONS = ['tv', 'pc']
const AUDIO_RATE_OPTIONS = ['44100', '48000', '96000']
const AUDIO_CHANNEL_OPTIONS = ['1', '2', '4', '6', '8']
const RESOLUTION_OPTIONS = ['1280x720', '1920x1080', '2560x1440', '2688x1152', '3840x2160']
const STRICTNESS_OPTIONS: StrictnessLevel[] = ['strict', 'warn', 'info', 'ignore']

const VALIDATION_FIELDS: {
  key: keyof ShowConfigData['validation_strictness']
  label: string
  autoIgnoreSpec?: SpecField
}[] = [
  { key: 'resolution', label: 'Resolution' },
  { key: 'framerate', label: 'Framerate', autoIgnoreSpec: 'framerate' },
  { key: 'codec', label: 'Codec' },
  { key: 'codec_flavor', label: 'Codec Flavor' },
  { key: 'color_space', label: 'Color Space', autoIgnoreSpec: 'color_space' },
  { key: 'color_range', label: 'Color Range', autoIgnoreSpec: 'color_range' },
  { key: 'audio_sample_rate', label: 'Audio Sample Rate', autoIgnoreSpec: 'audio_sample_rate' },
  { key: 'audio_channels', label: 'Audio Channels', autoIgnoreSpec: 'audio_channels' },
]

const FILENAME_VALIDATION_FIELDS: {
  key: keyof ShowConfigData['validation_strictness']
  label: string
  hint: string
  visible?: (config: ShowConfigData) => boolean
}[] = [
  {
    key: 'filename_convention',
    label: 'Convention match',
    hint: 'Filename does not match the delivery pattern at all',
  },
  {
    key: 'filename_format',
    label: 'Field format',
    hint: 'Recognisable pattern but malformed version, date, content, etc.',
  },
  {
    key: 'show_token',
    label: 'Show token match',
    hint: 'Show token in filename does not match Delivery show token',
    visible: conventionUsesShowToken,
  },
  {
    key: 'screen_id',
    label: 'Screen ID (in filename)',
    hint: 'Screen token is missing, unknown, or not in config',
  },
]

function cloneConfig(config: ShowConfigData): ShowConfigData {
  return JSON.parse(JSON.stringify(config)) as ShowConfigData
}

function selectToSpecNumber(value: string): number | null {
  if (value === '__na__') {
    return null
  }
  return Number(value)
}

function selectToSpecString(value: string): string | null {
  if (value === '__na__') {
    return null
  }
  return value
}

type SpecSelectProps = {
  label?: string
  value: number | string | null
  options: string[]
  numeric?: boolean
  onChange: (value: number | string | null) => void
  disabled?: boolean
  hint?: string
  compact?: boolean
}

function SpecSelect({
  label,
  value,
  options,
  numeric = false,
  onChange,
  disabled,
  hint,
  compact = false,
}: SpecSelectProps) {
  const customInputRef = useRef<HTMLInputElement>(null)
  const [pendingCustom, setPendingCustom] = useState(false)
  const isNa = value === null && !pendingCustom
  const inOptions = value !== null && options.includes(String(value))
  const selectValue = pendingCustom
    ? '__custom__'
    : value === null
      ? '__na__'
      : inOptions
        ? String(value)
        : '__custom__'
  const showCustomInput = selectValue === '__custom__'
  const customText = pendingCustom && value === null ? '' : value === null ? '' : String(value)

  useEffect(() => {
    if (showCustomInput) {
      customInputRef.current?.focus()
    }
  }, [showCustomInput])

  function applyCustomInput(raw: string) {
    if (numeric) {
      onChange(raw === '' ? null : Number(raw))
      return
    }
    onChange(raw === '' ? null : raw)
  }

  return (
    <label className={`field config-spec-field${compact ? ' config-spec-field-compact' : ''}`}>
      {label ? <span>{label}</span> : null}
      <select
        value={selectValue}
        onChange={(event) => {
          const next = event.target.value
          if (next === '__custom__') {
            setPendingCustom(true)
            return
          }
          setPendingCustom(false)
          onChange(numeric ? selectToSpecNumber(next) : selectToSpecString(next))
        }}
        disabled={disabled}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
        <option value="__na__">N/A</option>
        <option value="__custom__">Custom…</option>
      </select>
      {(showCustomInput || (!compact && isNa) || hint) && (
      <div className="config-spec-slot">
        {showCustomInput ? (
          <input
            ref={customInputRef}
            type="text"
            className="config-spec-custom-input"
            value={customText}
            placeholder={numeric ? 'Enter value' : 'Enter custom value'}
            onChange={(event) => {
              setPendingCustom(false)
              applyCustomInput(event.target.value)
            }}
            disabled={disabled}
          />
        ) : !compact && isNa ? (
          <span className="field-hint config-spec-slot-hint">Validation ignored for this field</span>
        ) : hint ? (
          <span className="field-hint config-spec-slot-hint">{hint}</span>
        ) : null}
      </div>
      )}
    </label>
  )
}

type CodecTagsProps = {
  title: string
  description: string
  codecs: string[]
  variant: 'expected' | 'preferred'
  availableCodecs: string[]
  onChange: (codecs: string[]) => void
  error?: string
}

function CodecTags({
  title,
  description,
  codecs,
  variant,
  availableCodecs,
  onChange,
  error,
}: CodecTagsProps) {
  const [selectedCodec, setSelectedCodec] = useState('')
  const [customCodec, setCustomCodec] = useState('')
  const [showCustom, setShowCustom] = useState(false)
  const customInputRef = useRef<HTMLInputElement>(null)

  const addOptions = useMemo(
    () => availableCodecs.filter((codec) => !codecs.includes(codec)),
    [availableCodecs, codecs],
  )

  useEffect(() => {
    if (showCustom) {
      customInputRef.current?.focus()
    }
  }, [showCustom])

  function addCodec() {
    const codec = showCustom ? customCodec.trim() : selectedCodec
    if (!codec || codecs.includes(codec)) {
      return
    }
    onChange([...codecs, codec])
    setSelectedCodec('')
    setCustomCodec('')
    setShowCustom(false)
  }

  return (
    <div className="config-codec-section">
      <div className="config-section-heading">
        <strong>{title}</strong>
        <span className="field-hint">{description}</span>
      </div>
      <div className="config-codec-tags">
        {codecs.map((codec) => (
          <span key={codec} className={`config-codec-tag config-codec-tag-${variant}`}>
            <code>{codec}</code>
            <button
              type="button"
              className="config-codec-remove"
              onClick={() => onChange(codecs.filter((item) => item !== codec))}
              aria-label={`Remove ${codec}`}
            >
              ✕
            </button>
          </span>
        ))}
      </div>
      <div className="config-codec-add">
        {showCustom ? (
          <input
            ref={customInputRef}
            type="text"
            value={customCodec}
            onChange={(event) => setCustomCodec(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                addCodec()
              }
            }}
            placeholder="Custom codec identifier"
          />
        ) : (
          <select
            value={selectedCodec}
            onChange={(event) => {
              const next = event.target.value
              if (next === '__custom__') {
                setShowCustom(true)
                setSelectedCodec('')
                setCustomCodec('')
                return
              }
              setSelectedCodec(next)
            }}
          >
            <option value="">Add codec…</option>
            {addOptions.map((codec) => (
              <option key={codec} value={codec}>
                {codec}
              </option>
            ))}
            <option value="__custom__">Custom…</option>
          </select>
        )}
        <button type="button" className="btn-secondary" onClick={() => addCodec()}>
          + Add
        </button>
        {showCustom && (
          <button
            type="button"
            className="btn-ghost"
            onClick={() => {
              setShowCustom(false)
              setCustomCodec('')
            }}
          >
            Use list
          </button>
        )}
      </div>
      {error && <span className="config-field-error">{error}</span>}
    </div>
  )
}

type ImageFormatSectionProps = {
  config: ShowConfigData
  onChange: (media: NonNullable<ShowConfigData['expected_media']>) => void
  error?: string
}

function ImageFormatSection({ config, onChange, error }: ImageFormatSectionProps) {
  const media = expectedMediaFrom(config)

  function toggleExtension(ext: string) {
    const selected = media.image_extensions.includes(ext)
    const next = selected
      ? media.image_extensions.filter((item) => item !== ext)
      : [...media.image_extensions, ext]
    onChange({ ...media, image_extensions: next })
  }

  return (
    <div className="config-still-section">
      <label className="field">
        <span>Accept still images in intake</span>
        <select
          value={media.accept_stills ? 'yes' : 'no'}
          onChange={(event) =>
            onChange({
              ...media,
              accept_stills: event.target.value === 'yes',
            })
          }
        >
          <option value="yes">Yes — stills and numbered sequences</option>
          <option value="no">No — video files only</option>
        </select>
        <span className="field-hint">
          Codec, framerate, and audio checks are skipped for stills. Resolution is still validated.
        </span>
      </label>

      {media.accept_stills && (
        <>
          <div className="config-section-heading">
            <strong>Accepted image formats</strong>
            <span className="field-hint">
              Click a format to enable or disable. Sequences are detected by numbered suffixes
              (e.g. _0001 … _0120).
            </span>
          </div>
          <div className="config-image-ext-tags">
            {DEFAULT_IMAGE_EXTENSIONS.map((ext) => {
              const selected = media.image_extensions.includes(ext)
              return (
                <button
                  key={ext}
                  type="button"
                  className={[
                    'config-image-ext-tag',
                    selected ? 'config-image-ext-tag-active' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={() => toggleExtension(ext)}
                  aria-pressed={selected}
                >
                  <code>{ext}</code>
                </button>
              )
            })}
          </div>

          <label className="field">
            <span>Numbered image sequences</span>
            <select
              value={media.allow_image_sequences ? 'group' : 'individual'}
              onChange={(event) =>
                onChange({
                  ...media,
                  allow_image_sequences: event.target.value === 'group',
                })
              }
            >
              <option value="group">Group frames as one asset in intake</option>
              <option value="individual">Treat each frame as a separate file</option>
            </select>
            <span className="field-hint">
              Grouped sequences validate once and copy all frames together.
            </span>
          </label>
        </>
      )}

      {error && <span className="config-field-error">{error}</span>}
    </div>
  )
}

type FilenameTokenBuilderProps = {
  tokens: string[]
  onChange: (tokens: string[]) => void
  example: string
  error?: string
}

function FilenameTokenBuilder({ tokens, onChange, example, error }: FilenameTokenBuilderProps) {
  const [dragFromIndex, setDragFromIndex] = useState<number | null>(null)
  const [overIndex, setOverIndex] = useState<number | null>(null)
  const tokensRef = useRef(tokens)
  const onChangeRef = useRef(onChange)
  const dragFromRef = useRef<number | null>(null)
  const overRef = useRef<number | null>(null)

  tokensRef.current = tokens
  onChangeRef.current = onChange

  const unused = ALL_FILENAME_TOKENS.filter((token) => !tokens.includes(token))

  function reorderTokens(fromIndex: number, toIndex: number) {
    if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) {
      return
    }
    const reordered = [...tokensRef.current]
    const [item] = reordered.splice(fromIndex, 1)
    reordered.splice(toIndex, 0, item)
    onChangeRef.current(reordered)
  }

  function removeToken(index: number) {
    onChange(tokens.filter((_, itemIndex) => itemIndex !== index))
  }

  function addToken(token: FilenameTokenId) {
    if (tokens.includes(token)) {
      return
    }
    onChange([...tokens, token])
  }

  function resolveTokenIndex(clientX: number, clientY: number): number | null {
    const el = document.elementFromPoint(clientX, clientY)
    const tokenEl = el?.closest('[data-token-index]') as HTMLElement | null
    if (!tokenEl) {
      return null
    }
    const index = Number(tokenEl.dataset.tokenIndex)
    return Number.isNaN(index) ? null : index
  }

  function beginPointerDrag(index: number, event: React.PointerEvent<HTMLSpanElement>) {
    if (event.button !== 0) {
      return
    }
    event.preventDefault()
    dragFromRef.current = index
    overRef.current = index
    setDragFromIndex(index)
    setOverIndex(index)
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  useEffect(() => {
    if (dragFromIndex === null) {
      return
    }

    function finishPointerDrag() {
      const from = dragFromRef.current
      const to = overRef.current
      if (from !== null && to !== null) {
        reorderTokens(from, to)
      }
      dragFromRef.current = null
      overRef.current = null
      setDragFromIndex(null)
      setOverIndex(null)
    }

    function handlePointerMove(event: PointerEvent) {
      const index = resolveTokenIndex(event.clientX, event.clientY)
      if (index === null || dragFromRef.current === null) {
        return
      }
      overRef.current = index
      setOverIndex(index)
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', finishPointerDrag)
    window.addEventListener('pointercancel', finishPointerDrag)
    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', finishPointerDrag)
      window.removeEventListener('pointercancel', finishPointerDrag)
    }
  }, [dragFromIndex])

  return (
    <div className="config-filename-section">
      <div className="config-section-heading">
        <strong>Filename pattern</strong>
        <span className="field-hint">Drag tokens to reorder · Click ✕ to move back to available</span>
      </div>

      {tokens.length === 0 ? (
        <p className="config-screens-lead">Click tokens below to build the pattern.</p>
      ) : (
        <div className="config-filename-pattern" role="list" aria-label="Filename token order">
          {tokens.map((token, index) => {
            const meta = FILENAME_TOKEN_META[token as FilenameTokenId]
            if (!meta) {
              return null
            }
            const isDragging = dragFromIndex === index
            const isDropTarget = overIndex === index && dragFromIndex !== null && dragFromIndex !== index
            return (
              <div key={token} className="config-filename-pattern-item" role="listitem">
                {index > 0 && <span className="config-filename-separator" aria-hidden="true">→</span>}
                <span
                  className={[
                    'config-filename-token',
                    'config-filename-token-active',
                    isDragging ? 'config-filename-token-dragging' : '',
                    isDropTarget ? 'config-filename-token-drop-target' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  title={meta.hint}
                  data-token-index={index}
                  onPointerDown={(event) => {
                    if ((event.target as HTMLElement).closest('button')) {
                      return
                    }
                    beginPointerDrag(index, event)
                  }}
                >
                  <span className="config-filename-drag-handle" aria-hidden="true">
                    ⠿
                  </span>
                  <span className="config-filename-token-pos">{index + 1}</span>
                  <span className="config-filename-token-text">
                    <code>{token}</code>
                    <span className="config-filename-token-label">{meta.label}</span>
                  </span>
                  <button
                    type="button"
                    className="config-codec-remove"
                    onClick={() => removeToken(index)}
                    aria-label={`Remove ${meta.label} from pattern`}
                  >
                    ✕
                  </button>
                </span>
              </div>
            )
          })}
        </div>
      )}

      <div className="config-section-heading">
        <strong>Available tokens</strong>
        <span className="field-hint">Click to append to the pattern</span>
      </div>
      <div className="config-filename-available">
        {unused.length === 0 ? (
          <span className="config-screens-lead">All tokens are in the pattern.</span>
        ) : (
          unused.map((token) => {
            const meta = FILENAME_TOKEN_META[token]
            return (
              <button
                key={token}
                type="button"
                className="config-filename-available-token"
                title={meta.hint}
                onClick={() => addToken(token)}
              >
                <code>{token}</code>
                <span>{meta.label}</span>
              </button>
            )
          })
        )}
      </div>

      <p className="config-screens-lead">
        Example: <code>{example}</code>
      </p>
      {error && <span className="config-field-error">{error}</span>}
    </div>
  )
}

export function ConfigView({ show, onSaved, onDirtyChange }: ConfigViewProps) {
  const [activeTab, setActiveTab] = useState<ConfigTab>('info')
  const [config, setConfig] = useState<ShowConfigData | null>(null)
  const [baseline, setBaseline] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [toast, setToast] = useState<string | null>(null)
  const [presets, setPresets] = useState<{ builtin: PresetData[]; custom: PresetData[] }>({
    builtin: [],
    custom: [],
  })
  const [codecOptions, setCodecOptions] = useState<string[]>([])
  const [selectedPreset, setSelectedPreset] = useState('')
  const [savePresetName, setSavePresetName] = useState('')
  const [showSavePreset, setShowSavePreset] = useState(false)

  const dirty = useMemo(() => {
    if (!config) {
      return false
    }
    return JSON.stringify(config) !== baseline
  }, [config, baseline])

  const exampleFilename = useMemo(
    () => (config ? buildExampleFilename(config) : ''),
    [config],
  )

  useEffect(() => {
    onDirtyChange?.(dirty)
  }, [dirty, onDirtyChange])

  const loadEditor = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [configData, presetData, codecData] = await Promise.all([
        fetchShowConfig(show.path),
        fetchPresets(),
        fetchCodecIdentifiers(),
      ])
      const cloned = cloneConfig({
        ...configData,
        intake: configData.intake ?? { mode: 'routed' },
        output_specs: configData.output_specs ?? { mode: 'uniform' },
        delivery: configData.delivery ?? { show_token: '' },
        filename_convention: configData.filename_convention ?? { enabled: false },
        validation_strictness: {
          filename_convention: 'strict',
          filename_format: 'warn',
          show_token: 'strict',
          screen_id: 'strict',
          ...configData.validation_strictness,
        },
      })
      if (isPerScreenOutput(cloned)) {
        const template = screenSpecsFromShow(cloned)
        cloned.screens = cloned.screens.map((screen) => ({
          ...screen,
          expected_specs: screen.expected_specs ?? { ...template },
        }))
      }
      setConfig(cloned)
      setBaseline(JSON.stringify(cloned))
      setPresets(presetData)
      setCodecOptions(codecData.identifiers)
      setSelectedPreset('')
      setFieldErrors({})
    } catch (err) {
      setError(formatConfigError(err))
    } finally {
      setLoading(false)
    }
  }, [show.path])

  useEffect(() => {
    void loadEditor()
  }, [loadEditor])

  useEffect(() => {
    if (!toast) {
      return
    }
    const timer = window.setTimeout(() => setToast(null), 3500)
    return () => window.clearTimeout(timer)
  }, [toast])

  function updateConfig(updater: (current: ShowConfigData) => ShowConfigData) {
    setConfig((current) => (current ? updater(current) : current))
  }

  function syncAutoIgnore(next: ShowConfigData): ShowConfigData {
    const strictness = { ...next.validation_strictness }
    for (const field of VALIDATION_FIELDS) {
      if (!field.autoIgnoreSpec) {
        continue
      }
      if (isSpecNa(next, field.autoIgnoreSpec)) {
        strictness[field.key] = 'ignore'
      }
    }
    return { ...next, validation_strictness: strictness }
  }

  function handleOutputModeChange(nextMode: 'uniform' | 'per_screen') {
    updateConfig((current) => {
      const prevMode = outputSpecsMode(current)
      if (nextMode === prevMode) {
        return current
      }
      if (nextMode === 'per_screen') {
        const template = screenSpecsFromShow(current)
        return syncAutoIgnore({
          ...current,
          output_specs: { mode: nextMode },
          screens: current.screens.map((screen) => ({
            ...screen,
            expected_specs: screen.expected_specs ?? { ...template },
          })),
        })
      }
      return syncAutoIgnore({
        ...current,
        output_specs: { mode: nextMode },
        screens: current.screens.map(({ expected_specs: _removed, ...screen }) => screen),
      })
    })
  }

  function handleConventionMode(mode: 'default' | 'custom') {
    const enabled = mode === 'custom'
    updateConfig((current) => ({
      ...current,
      filename_convention: {
        enabled,
        tokens: enabled
          ? current.filename_convention?.tokens?.length
            ? current.filename_convention.tokens
            : [...DEFAULT_FILENAME_TOKENS]
          : undefined,
        formats: enabled
          ? {
              version: { prefix: 'v' },
              date: 'YYYYMMDD',
              content: { allow_loop_suffix: true },
            }
          : undefined,
      },
    }))
  }

  function handleConventionTokens(tokens: string[]) {
    updateConfig((current) => ({
      ...current,
      filename_convention: {
        ...current.filename_convention,
        enabled: true,
        tokens,
        formats: current.filename_convention?.formats ?? {
          version: { prefix: 'v' },
          date: 'YYYYMMDD',
          content: { allow_loop_suffix: true },
        },
      },
    }))
  }

  function updateScreenVideoSpec(
    index: number,
    field: 'framerate' | 'color_space' | 'color_range',
    value: number | string | null,
  ) {
    updateConfig((current) => {
      const screens = [...current.screens]
      const row = { ...screens[index] }
      const base: ScreenExpectedSpecs = row.expected_specs ?? screenSpecsFromShow(current)
      if (field === 'framerate') {
        row.expected_specs = {
          ...base,
          framerate: typeof value === 'number' ? value : null,
        }
      } else if (field === 'color_space') {
        row.expected_specs = {
          ...base,
          color_space: typeof value === 'string' ? value : null,
        }
      } else {
        row.expected_specs = {
          ...base,
          color_range: typeof value === 'string' ? value : null,
        }
      }
      screens[index] = row
      return { ...current, screens }
    })
  }

  async function handleLoadPreset() {
    if (!config || !selectedPreset) {
      return
    }
    try {
      const result = await applyPreset(selectedPreset, config)
      const merged = syncAutoIgnore(cloneConfig(result.config))
      setConfig(merged)
      setToast(`✓ Loaded preset “${selectedPreset}”`)
      setFieldErrors({})
    } catch (err) {
      setToast(formatConfigError(err))
    }
  }

  async function handleImportPreset() {
    const filePath = await pickFileFromServer('Select preset JSON file')
    if (!filePath || !config) {
      return
    }
    try {
      const imported = await importPresetFile(filePath)
      const merged = syncAutoIgnore({
        ...config,
        expected_specs: { ...imported.expected_specs },
        expected_codecs: [...imported.expected_codecs],
        preferred_codecs: [...imported.preferred_codecs],
        validation_strictness: { ...imported.validation_strictness },
        preset: imported.preset_name,
      })
      setConfig(merged)
      setToast(`✓ Imported preset “${imported.preset_name}”`)
    } catch (err) {
      setToast(formatConfigError(err))
    }
  }

  async function handleSavePreset() {
    if (!config || !savePresetName.trim()) {
      return
    }
    try {
      await saveCustomPreset(savePresetName.trim(), buildConfigPayload(config))
      const presetData = await fetchPresets()
      setPresets(presetData)
      setShowSavePreset(false)
      setSavePresetName('')
      setToast(`✓ Preset “${savePresetName.trim()}” saved`)
    } catch (err) {
      setToast(formatConfigError(err))
    }
  }

  async function handleSave() {
    if (!config) {
      return
    }
    const validation = validateAll(config)
    if (validation) {
      setActiveTab(validation.tab)
      setFieldErrors(validation.errors)
      return
    }

    setSaving(true)
    setError(null)
    try {
      const payload = buildConfigPayload(config)
      await saveShowConfig(show.path, payload)
      setBaseline(JSON.stringify(payload))
      setConfig(payload)
      setFieldErrors({})
      setToast('✓ Configuration saved')
      onSaved({
        path: show.path,
        show_name: payload.show_name,
        preset: payload.preset,
        schema_version: payload.schema_version,
      })
    } catch (err) {
      setError(formatConfigError(err))
    } finally {
      setSaving(false)
    }
  }

  function handleCancel() {
    if (!dirty || window.confirm('You have unsaved changes. Discard them?')) {
      void loadEditor()
      setActiveTab('info')
    }
  }

  if (loading) {
    return <div className="config-loading">Loading configuration…</div>
  }

  if (!config) {
    return (
      <div className="config">
        {error && (
          <div className="banner banner-error" role="alert">
            {error}
          </div>
        )}
        <button type="button" className="btn-secondary" onClick={() => void loadEditor()}>
          Retry
        </button>
      </div>
    )
  }

  const perScreenOutput = isPerScreenOutput(config)

  return (
    <div className="config">
      <header className="config-header">
        <div>
          <h1>Edit Show Configuration</h1>
          <p className="config-subtitle">{show.show_name}</p>
        </div>
        {dirty && <span className="config-dirty-badge">Unsaved changes</span>}
      </header>

      {error && (
        <div className="banner banner-error" role="alert">
          {error}
        </div>
      )}

      <div className="config-tabs" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            className={`config-tab${activeTab === tab.id ? ' config-tab-active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="config-panel">
        {activeTab === 'info' && (
          <div className="config-form-grid">
            <label className="field">
              <span>Show Name</span>
              <input
                type="text"
                value={config.show_name}
                onChange={(event) =>
                  updateConfig((current) => ({ ...current, show_name: event.target.value }))
                }
              />
              {fieldErrors.show_name && (
                <span className="config-field-error">{fieldErrors.show_name}</span>
              )}
            </label>
            <ShowDateField
              value={config.show_date}
              onChange={(showDate) =>
                updateConfig((current) => ({ ...current, show_date: showDate }))
              }
              error={fieldErrors.show_date}
            />
            <h3 className="config-section-title">Operator</h3>
            <label className="field">
              <span>Company name</span>
              <input
                type="text"
                value={config.operator.company_name ?? ''}
                onChange={(event) =>
                  updateConfig((current) => ({
                    ...current,
                    operator: { ...current.operator, company_name: event.target.value },
                  }))
                }
                placeholder="Prestige AV"
              />
              <span className="field-hint">Appears in the delivery spec document header</span>
              {fieldErrors.company_name && (
                <span className="config-field-error">{fieldErrors.company_name}</span>
              )}
            </label>
            <div className="config-two-col">
              <label className="field">
                <span>Operator Name</span>
                <input
                  type="text"
                  value={config.operator.name}
                  onChange={(event) =>
                    updateConfig((current) => ({
                      ...current,
                      operator: { ...current.operator, name: event.target.value },
                    }))
                  }
                />
                {fieldErrors.operator_name && (
                  <span className="config-field-error">{fieldErrors.operator_name}</span>
                )}
              </label>
              <label className="field">
                <span>Operator Email</span>
                <input
                  type="email"
                  value={config.operator.email}
                  onChange={(event) =>
                    updateConfig((current) => ({
                      ...current,
                      operator: { ...current.operator, email: event.target.value },
                    }))
                  }
                />
                {fieldErrors.operator_email && (
                  <span className="config-field-error">{fieldErrors.operator_email}</span>
                )}
              </label>
            </div>
            <h3 className="config-section-title">Intake Mode</h3>
            <label className="field">
              <span>How files are routed during intake</span>
              <select
                value={config.intake?.mode ?? 'routed'}
                onChange={(event) =>
                  updateConfig((current) => ({
                    ...current,
                    intake: {
                      mode: event.target.value as 'routed' | 'flat',
                    },
                  }))
                }
              >
                <option value="routed">Routed — filename selects the screen folder</option>
                <option value="flat">Flat — validate against any screen; copy to _INCOMING</option>
              </select>
              <span className="config-screens-lead">
                Flat intake keeps original filenames. Passing files land in Media\_INCOMING;
                strict spec failures go to _REVIEW.
              </span>
            </label>
            <h3 className="config-section-title">Delivery</h3>
            <label className="field">
              <span>Show token (short show code for filenames)</span>
              <input
                type="text"
                value={config.delivery?.show_token ?? ''}
                onChange={(event) =>
                  updateConfig((current) => ({
                    ...current,
                    delivery: { ...current.delivery, show_token: event.target.value },
                  }))
                }
                placeholder="e.g. CorpEvent26"
              />
              <span className="config-screens-lead">
                Optional unless included in a custom filename convention.
              </span>
              {fieldErrors.show_token && (
                <span className="config-field-error">{fieldErrors.show_token}</span>
              )}
            </label>
            <label className="field">
              <span>Vendor notes (optional)</span>
              <textarea
                className="config-notes-textarea"
                rows={4}
                value={config.delivery?.vendor_notes ?? ''}
                onChange={(event) =>
                  updateConfig((current) => ({
                    ...current,
                    delivery: { ...current.delivery, vendor_notes: event.target.value },
                  }))
                }
                placeholder="Additional instructions for content creators — included in the delivery spec when set"
              />
              <span className="config-screens-lead">
                Appears in the generated delivery spec document before Key Rules.
              </span>
              {fieldErrors.vendor_notes && (
                <span className="config-field-error">{fieldErrors.vendor_notes}</span>
              )}
            </label>
          </div>
        )}

        {activeTab === 'specs' && (
          <div className="config-specs">
            <div className="config-preset-bar">
              <label className="field config-preset-select">
                <span>Preset</span>
                <select
                  value={selectedPreset}
                  onChange={(event) => setSelectedPreset(event.target.value)}
                >
                  <option value="">— Select a preset —</option>
                  <optgroup label="Built-in">
                    {presets.builtin.map((preset) => (
                      <option key={preset.preset_name} value={preset.preset_name}>
                        {preset.preset_name}
                      </option>
                    ))}
                  </optgroup>
                  {presets.custom.length > 0 && (
                    <optgroup label="Custom">
                      {presets.custom.map((preset) => (
                        <option key={preset.preset_name} value={preset.preset_name}>
                          {preset.preset_name}
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>
              </label>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => void handleLoadPreset()}
                disabled={!selectedPreset}
              >
                Load
              </button>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => setShowSavePreset((value) => !value)}
              >
                💾 Save as Preset
              </button>
              <button type="button" className="btn-ghost" onClick={() => void handleImportPreset()}>
                📁 Browse
              </button>
            </div>

            {showSavePreset && (
              <div className="config-preset-save-row">
                <input
                  type="text"
                  value={savePresetName}
                  onChange={(event) => setSavePresetName(event.target.value)}
                  placeholder="Preset name"
                />
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => void handleSavePreset()}
                  disabled={!savePresetName.trim()}
                >
                  Confirm
                </button>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => {
                    setShowSavePreset(false)
                    setSavePresetName('')
                  }}
                >
                  Cancel
                </button>
              </div>
            )}

            <h3 className="config-section-title">Output Specifications</h3>
            <label className="field">
              <span>Do all screens share the same video specs?</span>
              <select
                value={outputSpecsMode(config)}
                onChange={(event) =>
                  handleOutputModeChange(event.target.value as 'uniform' | 'per_screen')
                }
              >
                <option value="uniform">Same specs for all screens</option>
                <option value="per_screen">Specs vary by screen (LED + projector mix)</option>
              </select>
              <span className="config-screens-lead">
                {perScreenOutput
                  ? 'Set framerate, color space, and color range on the Screens tab for each output.'
                  : 'Framerate, color space, and color range below apply to every screen. Resolution is always per screen.'}
              </span>
            </label>

            <h3 className="config-section-title">Technical Specifications</h3>
            {!perScreenOutput ? (
              <div className="config-spec-grid">
                <SpecSelect
                  label="Framerate (fps)"
                  value={config.expected_specs.framerate}
                  options={FRAMERATE_OPTIONS}
                  numeric
                  onChange={(value) =>
                    updateConfig((current) =>
                      syncAutoIgnore({
                        ...current,
                        expected_specs: {
                          ...current.expected_specs,
                          framerate: typeof value === 'number' ? value : null,
                        },
                      }),
                    )
                  }
                />
                <SpecSelect
                  label="Color Space"
                  value={config.expected_specs.color_space}
                  options={COLOR_SPACE_OPTIONS}
                  onChange={(value) =>
                    updateConfig((current) =>
                      syncAutoIgnore({
                        ...current,
                        expected_specs: {
                          ...current.expected_specs,
                          color_space: typeof value === 'string' ? value : null,
                        },
                      }),
                    )
                  }
                />
                <SpecSelect
                  label="Color Range"
                  value={config.expected_specs.color_range}
                  options={COLOR_RANGE_OPTIONS}
                  onChange={(value) =>
                    updateConfig((current) =>
                      syncAutoIgnore({
                        ...current,
                        expected_specs: {
                          ...current.expected_specs,
                          color_range: typeof value === 'string' ? value : null,
                        },
                      }),
                    )
                  }
                />
                <SpecSelect
                  label="Audio Sample Rate"
                  value={config.expected_specs.audio_sample_rate}
                  options={AUDIO_RATE_OPTIONS}
                  numeric
                  onChange={(value) =>
                    updateConfig((current) =>
                      syncAutoIgnore({
                        ...current,
                        expected_specs: {
                          ...current.expected_specs,
                          audio_sample_rate: typeof value === 'number' ? value : null,
                        },
                      }),
                    )
                  }
                />
                <SpecSelect
                  label="Audio Channels"
                  value={config.expected_specs.audio_channels}
                  options={AUDIO_CHANNEL_OPTIONS}
                  numeric
                  onChange={(value) =>
                    updateConfig((current) =>
                      syncAutoIgnore({
                        ...current,
                        expected_specs: {
                          ...current.expected_specs,
                          audio_channels: typeof value === 'number' ? value : null,
                        },
                      }),
                    )
                  }
                />
              </div>
            ) : (
              <div className="config-spec-grid">
                <SpecSelect
                  label="Audio Sample Rate"
                  value={config.expected_specs.audio_sample_rate}
                  options={AUDIO_RATE_OPTIONS}
                  numeric
                  onChange={(value) =>
                    updateConfig((current) =>
                      syncAutoIgnore({
                        ...current,
                        expected_specs: {
                          ...current.expected_specs,
                          audio_sample_rate: typeof value === 'number' ? value : null,
                        },
                      }),
                    )
                  }
                />
                <SpecSelect
                  label="Audio Channels"
                  value={config.expected_specs.audio_channels}
                  options={AUDIO_CHANNEL_OPTIONS}
                  numeric
                  onChange={(value) =>
                    updateConfig((current) =>
                      syncAutoIgnore({
                        ...current,
                        expected_specs: {
                          ...current.expected_specs,
                          audio_channels: typeof value === 'number' ? value : null,
                        },
                      }),
                    )
                  }
                />
              </div>
            )}

            <h3 className="config-section-title">Filename Convention</h3>
            <label className="field">
              <span>Delivery filename pattern</span>
              <select
                value={conventionEnabled(config) ? 'custom' : 'default'}
                onChange={(event) =>
                  handleConventionMode(event.target.value as 'default' | 'custom')
                }
              >
                <option value="default">Default — SCR##_content_v##_YYYYMMDD</option>
                <option value="custom">Custom — build your own token order</option>
              </select>
              <span className="config-screens-lead">
                {conventionEnabled(config)
                  ? 'Drag tokens to set order. Original filenames are never renamed on intake.'
                  : (
                      <>
                        Example: <code>{exampleFilename}</code>
                      </>
                    )}
              </span>
            </label>
            {conventionEnabled(config) && (
              <FilenameTokenBuilder
                tokens={config.filename_convention?.tokens ?? [...DEFAULT_FILENAME_TOKENS]}
                onChange={handleConventionTokens}
                example={exampleFilename}
                error={fieldErrors.filename_convention}
              />
            )}

            <h3 className="config-section-title">Still images & sequences</h3>
            <ImageFormatSection
              config={config}
              onChange={(media) =>
                updateConfig((current) => ({
                  ...current,
                  expected_media: media,
                }))
              }
              error={fieldErrors.expected_media}
            />

            <h3 className="config-section-title">Codecs</h3>
            <CodecTags
              title="Expected Codecs"
              description="File must use one of these"
              codecs={config.expected_codecs}
              variant="expected"
              availableCodecs={codecOptions}
              onChange={(codecs) =>
                updateConfig((current) => ({ ...current, expected_codecs: codecs }))
              }
              error={fieldErrors.expected_codecs}
            />
            <CodecTags
              title="Preferred Codecs"
              description="No warning issued when file uses one of these"
              codecs={config.preferred_codecs}
              variant="preferred"
              availableCodecs={codecOptions}
              onChange={(codecs) =>
                updateConfig((current) => ({ ...current, preferred_codecs: codecs }))
              }
              error={fieldErrors.preferred_codecs}
            />
          </div>
        )}

        {activeTab === 'screens' && (
          <div className="config-screens">
            <div className="config-screens-header">
              <p className="config-screens-lead">
                Define output screens. IDs must be unique (e.g., SCR01).
                {perScreenOutput
                  ? ' Set framerate, color space, and color range per screen below.'
                  : ' Video specs are shared — configure them on the Expected Specs tab.'}
              </p>
              <button
                type="button"
                className="btn-secondary"
                onClick={() =>
                  updateConfig((current) => {
                    const newScreen: ShowConfigData['screens'][number] = {
                      id: '',
                      name: '',
                      resolution: RESOLUTION_OPTIONS[1],
                    }
                    if (isPerScreenOutput(current)) {
                      newScreen.expected_specs = screenSpecsFromShow(current)
                    }
                    return {
                      ...current,
                      screens: [...current.screens, newScreen],
                    }
                  })
                }
              >
                + Add Screen
              </button>
            </div>
            <div className="config-screen-table">
              <div
                className={`config-screen-row config-screen-head${perScreenOutput ? ' config-screen-row-per-screen' : ''}`}
              >
                <span className="config-screen-head-label">Screen ID</span>
                <span className="config-screen-head-label">Display Name</span>
                <span className="config-screen-head-label">Resolution</span>
                {perScreenOutput && (
                  <>
                    <span className="config-screen-head-label">Framerate</span>
                    <span className="config-screen-head-label">Color Space</span>
                    <span className="config-screen-head-label">Color Range</span>
                  </>
                )}
                <span className="config-screen-head-action" aria-hidden="true" />
              </div>
              {config.screens.map((screen, index) => (
                <div
                  key={index}
                  className={`config-screen-row${perScreenOutput ? ' config-screen-row-per-screen' : ''}`}
                >
                  <label className="field">
                    <input
                      type="text"
                      value={screen.id}
                      placeholder="SCR01"
                      onChange={(event) =>
                        updateConfig((current) => {
                          const screens = [...current.screens]
                          screens[index] = { ...screens[index], id: event.target.value }
                          return { ...current, screens }
                        })
                      }
                    />
                    {fieldErrors[`screen_${index}_id`] && (
                      <span className="config-field-error">{fieldErrors[`screen_${index}_id`]}</span>
                    )}
                  </label>
                  <label className="field">
                    <input
                      type="text"
                      value={screen.name ?? ''}
                      placeholder="HouseLeft"
                      onChange={(event) =>
                        updateConfig((current) => {
                          const screens = [...current.screens]
                          screens[index] = { ...screens[index], name: event.target.value }
                          return { ...current, screens }
                        })
                      }
                    />
                    {fieldErrors[`screen_${index}_name`] && (
                      <span className="config-field-error">
                        {fieldErrors[`screen_${index}_name`]}
                      </span>
                    )}
                  </label>
                  <label className="field">
                    <select
                      value={
                        screen.resolution && RESOLUTION_OPTIONS.includes(screen.resolution)
                          ? screen.resolution
                          : '__custom__'
                      }
                      onChange={(event) => {
                        const value = event.target.value
                        updateConfig((current) => {
                          const screens = [...current.screens]
                          screens[index] = {
                            ...screens[index],
                            resolution: value === '__custom__' ? '' : value,
                          }
                          return { ...current, screens }
                        })
                      }}
                    >
                      {RESOLUTION_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                      <option value="__custom__">Custom…</option>
                    </select>
                    {(!screen.resolution ||
                      !RESOLUTION_OPTIONS.includes(screen.resolution ?? '')) && (
                      <input
                        type="text"
                        value={screen.resolution ?? ''}
                        placeholder="3840x816"
                        onChange={(event) =>
                          updateConfig((current) => {
                            const screens = [...current.screens]
                            screens[index] = {
                              ...screens[index],
                              resolution: event.target.value,
                            }
                            return { ...current, screens }
                          })
                        }
                      />
                    )}
                    {fieldErrors[`screen_${index}_resolution`] && (
                      <span className="config-field-error">
                        {fieldErrors[`screen_${index}_resolution`]}
                      </span>
                    )}
                  </label>
                  {perScreenOutput && (
                    <>
                      <SpecSelect
                        compact
                        value={screen.expected_specs?.framerate ?? null}
                        options={FRAMERATE_OPTIONS}
                        numeric
                        onChange={(value) => updateScreenVideoSpec(index, 'framerate', value)}
                      />
                      <SpecSelect
                        compact
                        value={screen.expected_specs?.color_space ?? null}
                        options={COLOR_SPACE_OPTIONS}
                        onChange={(value) => updateScreenVideoSpec(index, 'color_space', value)}
                      />
                      <SpecSelect
                        compact
                        value={screen.expected_specs?.color_range ?? null}
                        options={COLOR_RANGE_OPTIONS}
                        onChange={(value) => updateScreenVideoSpec(index, 'color_range', value)}
                      />
                    </>
                  )}
                  <button
                    type="button"
                    className="config-screen-delete"
                    onClick={() =>
                      updateConfig((current) => ({
                        ...current,
                        screens: current.screens.filter((_, rowIndex) => rowIndex !== index),
                      }))
                    }
                    aria-label="Delete screen"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>

            {config.screens.length > 0 && (
              <div className="config-screen-notes-section">
                <h3 className="config-section-title">Screen configuration notes</h3>
                <p className="config-screens-lead">
                  Appears below the Screen Configuration table in the delivery spec. The Notes
                  column in the table is left blank for you to fill in manually in Word after
                  generation.
                </p>
                <label className="field">
                  <textarea
                    className="config-notes-textarea"
                    rows={4}
                    value={config.delivery?.optional_screen_notes ?? ''}
                    placeholder={DEFAULT_SCREEN_NOTES}
                    onChange={(event) =>
                      updateConfig((current) => ({
                        ...current,
                        delivery: {
                          ...current.delivery,
                          optional_screen_notes: event.target.value,
                        },
                      }))
                    }
                  />
                  {fieldErrors.optional_screen_notes && (
                    <span className="config-field-error">
                      {fieldErrors.optional_screen_notes}
                    </span>
                  )}
                </label>
              </div>
            )}
          </div>
        )}

        {activeTab === 'validation' && (
          <div className="config-validation">
            <p className="config-screens-lead">
              Control how strictly each property is validated during intake.
              {perScreenOutput
                ? ' Framerate and color checks use each screen’s values from the Screens tab.'
                : ' Fields set to N/A in Expected Specs are automatically marked Ignore here.'}
            </p>
            <div className="config-legend">
              <span className="config-legend-strict">Strict</span> = reject to _REVIEW
              <span className="config-legend-warn">Warn</span> = copy with warning
              <span className="config-legend-info">Info</span> = log only
              <span className="config-legend-ignore">Ignore</span> = skip check
            </div>

            <h3 className="config-section-title">Filename validation</h3>
            <p className="config-screens-lead">
              Example: <code>{exampleFilename}</code>
              {(config.intake?.mode ?? 'routed') === 'flat'
                ? ' Flat intake never blocks routing on filename issues — warnings only.'
                : ''}
            </p>
            <div className="config-validation-grid">
              {FILENAME_VALIDATION_FIELDS.filter(
                (field) => !field.visible || field.visible(config),
              ).map((field) => (
                <label key={field.key} className="field">
                  <span title={field.hint}>{field.label}</span>
                  <select
                    value={config.validation_strictness[field.key] ?? 'strict'}
                    onChange={(event) =>
                      updateConfig((current) => ({
                        ...current,
                        validation_strictness: {
                          ...current.validation_strictness,
                          [field.key]: event.target.value,
                        },
                      }))
                    }
                  >
                    {STRICTNESS_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>

            <h3 className="config-section-title">Media spec validation</h3>
            <div className="config-validation-grid">
              {VALIDATION_FIELDS.map((field) => {
                const autoIgnore =
                  field.autoIgnoreSpec !== undefined && isSpecNa(config, field.autoIgnoreSpec)
                return (
                  <label key={field.key} className="field">
                    <span>{field.label}</span>
                    <select
                      value={config.validation_strictness[field.key] ?? 'strict'}
                      disabled={autoIgnore}
                      title={
                        autoIgnore
                          ? 'Auto-set to Ignore because the expected spec is N/A'
                          : undefined
                      }
                      onChange={(event) =>
                        updateConfig((current) => ({
                          ...current,
                          validation_strictness: {
                            ...current.validation_strictness,
                            [field.key]: event.target.value,
                          },
                        }))
                      }
                    >
                      {STRICTNESS_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </label>
                )
              })}
            </div>
          </div>
        )}
      </div>

      <footer className="config-footer">
        <button
          type="button"
          className="config-link-btn"
          onClick={() => void openShowConfig(show.path)}
        >
          📝 Open raw config in text editor
        </button>
        <div className="config-footer-actions">
          {toast && <span className="config-toast">{toast}</span>}
          <button type="button" className="btn-secondary" onClick={handleCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => void handleSave()}
            disabled={saving}
          >
            {saving ? 'Saving…' : '💾 Save Configuration'}
          </button>
        </div>
      </footer>
    </div>
  )
}
