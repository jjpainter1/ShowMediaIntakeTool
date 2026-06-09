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
  type ShowConfigData,
  type ShowSummary,
} from '../lib/api'
import {
  buildConfigPayload,
  isSpecNa,
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
  { key: 'screen_id', label: 'Screen ID' },
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
  label: string
  value: number | string | null
  options: string[]
  numeric?: boolean
  onChange: (value: number | string | null) => void
  disabled?: boolean
  hint?: string
}

function SpecSelect({
  label,
  value,
  options,
  numeric = false,
  onChange,
  disabled,
  hint,
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
    <label className="field config-spec-field">
      <span>{label}</span>
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
        ) : isNa ? (
          <span className="field-hint config-spec-slot-hint">Validation ignored for this field</span>
        ) : hint ? (
          <span className="field-hint config-spec-slot-hint">{hint}</span>
        ) : null}
      </div>
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
      const cloned = cloneConfig(configData)
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

            <h3 className="config-section-title">Technical Specifications</h3>
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
                Define output screens. IDs must be unique (e.g., SCR01). Screen additions update
                the Dashboard after saving.
              </p>
              <button
                type="button"
                className="btn-secondary"
                onClick={() =>
                  updateConfig((current) => ({
                    ...current,
                    screens: [
                      ...current.screens,
                      { id: '', name: '', resolution: RESOLUTION_OPTIONS[1] },
                    ],
                  }))
                }
              >
                + Add Screen
              </button>
            </div>
            <div className="config-screen-table">
              <div className="config-screen-row config-screen-head">
                <span>Screen ID</span>
                <span>Display Name</span>
                <span>Resolution</span>
                <span />
              </div>
              {config.screens.map((screen, index) => (
                <div key={index} className="config-screen-row">
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
          </div>
        )}

        {activeTab === 'validation' && (
          <div className="config-validation">
            <p className="config-screens-lead">
              Control how strictly each property is validated during intake. Fields set to N/A in
              Expected Specs are automatically marked Ignore here.
            </p>
            <div className="config-legend">
              <span className="config-legend-strict">Strict</span> = reject to _REVIEW
              <span className="config-legend-warn">Warn</span> = copy with warning
              <span className="config-legend-info">Info</span> = log only
              <span className="config-legend-ignore">Ignore</span> = skip check
            </div>
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
