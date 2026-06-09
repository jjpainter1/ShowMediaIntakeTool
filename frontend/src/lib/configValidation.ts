import type { ShowConfigData } from './api'

export type StrictnessLevel = 'strict' | 'warn' | 'info' | 'ignore'

export type ConfigTab = 'info' | 'specs' | 'screens' | 'validation'

export type FieldErrors = Record<string, string>

const FILENAME_SAFE = /^[A-Za-z0-9_-]+$/
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/
const RESOLUTION_RE = /^\d+x\d+$/

export function isFilenameSafe(value: string): boolean {
  return FILENAME_SAFE.test(value)
}

export function isValidDate(value: string): boolean {
  if (!DATE_RE.test(value)) {
    return false
  }
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(year, month - 1, day)
  return (
    date.getFullYear() === year &&
    date.getMonth() === month - 1 &&
    date.getDate() === day
  )
}

export function isValidEmail(value: string): boolean {
  return value.includes('@') && value.trim().length > 0
}

export function isValidResolution(value: string): boolean {
  return !value || RESOLUTION_RE.test(value)
}

export function specFieldKey(
  field: keyof ShowConfigData['expected_specs'],
): keyof ShowConfigData['validation_strictness'] | null {
  const map: Record<string, keyof ShowConfigData['validation_strictness']> = {
    framerate: 'framerate',
    color_space: 'color_space',
    color_range: 'color_range',
    audio_sample_rate: 'audio_sample_rate',
    audio_channels: 'audio_channels',
  }
  return map[field] ?? null
}

export function isSpecNa(config: ShowConfigData, field: keyof ShowConfigData['expected_specs']): boolean {
  return config.expected_specs[field] === null
}

export function validateShowInfo(config: ShowConfigData): FieldErrors {
  const errors: FieldErrors = {}
  if (!config.show_name.trim()) {
    errors.show_name = 'Show name is required'
  } else if (!isFilenameSafe(config.show_name)) {
    errors.show_name = 'Only letters, digits, hyphens, and underscores'
  }
  if (!config.show_date.trim()) {
    errors.show_date = 'Show date is required'
  } else if (!isValidDate(config.show_date)) {
    errors.show_date = 'Use YYYY-MM-DD with a valid calendar date'
  }
  if (!config.operator.name.trim()) {
    errors.operator_name = 'Operator name is required'
  }
  if (!config.operator.email.trim()) {
    errors.operator_email = 'Operator email is required'
  } else if (!isValidEmail(config.operator.email)) {
    errors.operator_email = 'Email must contain @'
  }
  return errors
}

export function validateExpectedSpecs(config: ShowConfigData): FieldErrors {
  const errors: FieldErrors = {}
  if (!config.expected_codecs.length) {
    errors.expected_codecs = 'Add at least one expected codec'
  }
  if (!config.preferred_codecs.length) {
    errors.preferred_codecs = 'Add at least one preferred codec'
  }
  const unexpected = config.preferred_codecs.filter(
    (codec) => !config.expected_codecs.includes(codec),
  )
  if (unexpected.length) {
    errors.preferred_codecs = `Not in expected codecs: ${unexpected.join(', ')}`
  }
  return errors
}

export function validateScreens(config: ShowConfigData): FieldErrors {
  const errors: FieldErrors = {}
  const seen = new Set<string>()
  config.screens.forEach((screen, index) => {
    const id = screen.id.trim()
    if (!id) {
      errors[`screen_${index}_id`] = 'Screen ID is required'
    } else if (!isFilenameSafe(id)) {
      errors[`screen_${index}_id`] = 'Only letters, digits, hyphens, and underscores'
    } else if (seen.has(id)) {
      errors[`screen_${index}_id`] = `Duplicate screen ID: ${id}`
    } else {
      seen.add(id)
    }
    if (screen.name?.trim() && !isFilenameSafe(screen.name.trim())) {
      errors[`screen_${index}_name`] = 'Only letters, digits, hyphens, and underscores'
    }
    const resolution = screen.resolution?.trim() ?? ''
    if (resolution && !isValidResolution(resolution)) {
      errors[`screen_${index}_resolution`] = 'Use ####x#### format'
    }
  })
  return errors
}

export function validateAll(config: ShowConfigData): { tab: ConfigTab; errors: FieldErrors } | null {
  const info = validateShowInfo(config)
  if (Object.keys(info).length) {
    return { tab: 'info', errors: info }
  }
  const specs = validateExpectedSpecs(config)
  if (Object.keys(specs).length) {
    return { tab: 'specs', errors: specs }
  }
  const screens = validateScreens(config)
  if (Object.keys(screens).length) {
    return { tab: 'screens', errors: screens }
  }
  return null
}

export function buildConfigPayload(config: ShowConfigData): ShowConfigData {
  return {
    ...config,
    schema_version: 2,
    show_name: config.show_name.trim(),
    show_date: config.show_date.trim(),
    operator: {
      name: config.operator.name.trim(),
      email: config.operator.email.trim(),
    },
    expected_specs: { ...config.expected_specs },
    expected_codecs: [...config.expected_codecs],
    preferred_codecs: [...config.preferred_codecs],
    screens: config.screens.map((screen) => ({
      id: screen.id.trim(),
      ...(screen.name?.trim() ? { name: screen.name.trim() } : {}),
      ...(screen.resolution?.trim() ? { resolution: screen.resolution.trim() } : {}),
    })),
    validation_strictness: { ...config.validation_strictness },
  }
}
