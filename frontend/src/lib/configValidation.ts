import type { ScreenExpectedSpecs, ShowConfigData } from './api'

export type StrictnessLevel = 'strict' | 'warn' | 'info' | 'ignore'

export type ConfigTab = 'info' | 'specs' | 'screens' | 'validation'

export type FieldErrors = Record<string, string>

const FILENAME_SAFE = /^[A-Za-z0-9_-]+$/
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/
const RESOLUTION_RE = /^\d+x\d+$/

export const DEFAULT_FILENAME_TOKENS = ['screen', 'content', 'version', 'date'] as const

export const REQUIRED_FILENAME_TOKENS = ['screen', 'content', 'version', 'date'] as const

export const ALL_FILENAME_TOKENS = [
  'show_token',
  'initials',
  'screen',
  'content',
  'version',
  'date',
] as const

export type FilenameTokenId = (typeof ALL_FILENAME_TOKENS)[number]

export const FILENAME_TOKEN_META: Record<
  FilenameTokenId,
  { label: string; hint: string; optional: boolean }
> = {
  show_token: {
    label: 'Show token',
    hint: 'Short show code from Delivery (Show Info tab)',
    optional: true,
  },
  initials: {
    label: 'Artist initials',
    hint: '2–3 letters per file — not validated against config',
    optional: true,
  },
  screen: {
    label: 'Screen',
    hint: 'Routes file to the matching screen folder',
    optional: false,
  },
  content: {
    label: 'Content',
    hint: 'Asset slug; optional -LOOP suffix',
    optional: false,
  },
  version: {
    label: 'Version',
    hint: 'e.g. v01, v02',
    optional: false,
  },
  date: {
    label: 'Date',
    hint: 'YYYYMMDD delivery date',
    optional: false,
  },
}

export function conventionTokens(config: ShowConfigData): string[] {
  return config.filename_convention?.tokens ?? [...DEFAULT_FILENAME_TOKENS]
}

export function conventionUsesShowToken(config: ShowConfigData): boolean {
  return conventionEnabled(config) && conventionTokens(config).includes('show_token')
}

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

export function outputSpecsMode(config: ShowConfigData): 'uniform' | 'per_screen' {
  return config.output_specs?.mode ?? 'uniform'
}

export function isPerScreenOutput(config: ShowConfigData): boolean {
  return outputSpecsMode(config) === 'per_screen'
}

export function conventionEnabled(config: ShowConfigData): boolean {
  return Boolean(config.filename_convention?.enabled)
}

export const DEFAULT_SCREEN_NOTES =
  "See attached screen diagram for physical placement and template files for each screen's exact pixel dimensions"

export function buildFilenamePattern(config: ShowConfigData): string {
  const tokens = conventionEnabled(config)
    ? conventionTokens(config)
    : [...DEFAULT_FILENAME_TOKENS]
  return `${tokens.map((token) => `{${token}}`).join('_')}.ext`
}

export function buildExampleFilename(config: ShowConfigData): string {
  const tokens = conventionEnabled(config)
    ? conventionTokens(config)
    : [...DEFAULT_FILENAME_TOKENS]
  const showToken = config.delivery?.show_token?.trim() || 'ShowToken'
  const screenId = config.screens[0]?.id ?? 'SCR01'
  const parts = tokens.map((token) => {
    switch (token) {
      case 'show_token':
        return showToken
      case 'initials':
        return 'ABC'
      case 'screen':
        return screenId
      case 'content':
        return 'OpeningVideo-LOOP'
      case 'version':
        return 'v01'
      case 'date':
        return '20260425'
      default:
        return token
    }
  })
  return `${parts.join('_')}.mov`
}

export function emptyScreenExpectedSpecs(): ScreenExpectedSpecs {
  return {
    framerate: null,
    color_space: null,
    color_range: null,
    audio_sample_rate: null,
    audio_channels: null,
  }
}

/** Copy show-level video specs for seeding per-screen rows. */
export function screenSpecsFromShow(config: ShowConfigData): ScreenExpectedSpecs {
  return {
    framerate: config.expected_specs.framerate,
    color_space: config.expected_specs.color_space,
    color_range: config.expected_specs.color_range,
    audio_sample_rate: null,
    audio_channels: null,
  }
}

export function isSpecNa(config: ShowConfigData, field: keyof ShowConfigData['expected_specs']): boolean {
  if (isPerScreenOutput(config) && (field === 'framerate' || field === 'color_space' || field === 'color_range')) {
    return true
  }
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
  if (!config.operator.company_name?.trim()) {
    errors.company_name = 'Company name is required for the delivery spec'
  }
  if (!config.operator.name.trim()) {
    errors.operator_name = 'Operator name is required'
  }
  if (!config.operator.email.trim()) {
    errors.operator_email = 'Operator email is required'
  } else if (!isValidEmail(config.operator.email)) {
    errors.operator_email = 'Email must contain @'
  }
  const showToken = config.delivery?.show_token?.trim() ?? ''
  if (showToken && !isFilenameSafe(showToken)) {
    errors.show_token = 'Only letters, digits, hyphens, and underscores'
  }
  const vendorNotes = config.delivery?.vendor_notes ?? ''
  if (vendorNotes.length > 4000) {
    errors.vendor_notes = 'Vendor notes must be 4000 characters or fewer'
  }
  const optionalScreenNotes = config.delivery?.optional_screen_notes ?? ''
  if (optionalScreenNotes.length > 2000) {
    errors.optional_screen_notes = 'Screen notes must be 2000 characters or fewer'
  }
  if (
    conventionEnabled(config) &&
    conventionTokens(config).includes('show_token') &&
    !showToken
  ) {
    errors.show_token = 'Show token is required when included in the filename convention'
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
  if (conventionEnabled(config)) {
    const tokens = conventionTokens(config)
    const tokenSet = new Set(tokens)
    if (tokenSet.size !== tokens.length) {
      errors.filename_convention = 'Each token can only appear once in the pattern'
    }
    const missingRequired = REQUIRED_FILENAME_TOKENS.filter((token) => !tokenSet.has(token))
    if (missingRequired.length) {
      errors.filename_convention = `Pattern must include: ${missingRequired.map((t) => FILENAME_TOKEN_META[t].label).join(', ')}`
    }
    const intakeMode = config.intake?.mode ?? 'routed'
    if (intakeMode === 'routed' && !tokens.includes('screen')) {
      errors.filename_convention = 'Screen token is required for routed intake'
    }
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
    if (isPerScreenOutput(config) && id && !screen.expected_specs) {
      errors[`screen_${index}_specs`] = 'Output specs block missing for screen'
    }
  })
  if (config.intake?.mode === 'flat' && config.screens.length === 0) {
    errors.screens = 'Add at least one screen for flat intake mode'
  }
  return errors
}

export function validateAll(config: ShowConfigData): { tab: ConfigTab; errors: FieldErrors } | null {
  const info = validateShowInfo(config)
  const specs = validateExpectedSpecs(config)
  const screens = validateScreens(config)
  const errors = { ...info, ...specs, ...screens }
  if (!Object.keys(errors).length) {
    return null
  }
  if (Object.keys(info).length) {
    return { tab: 'info', errors }
  }
  if (Object.keys(specs).length) {
    return { tab: 'specs', errors }
  }
  return { tab: 'screens', errors }
}

export function buildConfigPayload(config: ShowConfigData): ShowConfigData {
  const intakeMode = config.intake?.mode ?? 'routed'
  const outputMode = outputSpecsMode(config)
  const perScreen = outputMode === 'per_screen'
  const conventionOn = conventionEnabled(config)
  const showToken = config.delivery?.show_token?.trim() ?? ''
  const vendorNotes = config.delivery?.vendor_notes?.trim() ?? ''
  const optionalScreenNotes = config.delivery?.optional_screen_notes?.trim() ?? ''
  const patternTokens = conventionOn ? conventionTokens(config) : [...DEFAULT_FILENAME_TOKENS]
  const delivery: NonNullable<ShowConfigData['delivery']> = {}
  if (showToken) {
    delivery.show_token = showToken
  }
  if (optionalScreenNotes) {
    delivery.optional_screen_notes = optionalScreenNotes
  }
  if (vendorNotes) {
    delivery.vendor_notes = vendorNotes
  }
  return {
    ...config,
    schema_version: 2,
    show_name: config.show_name.trim(),
    show_date: config.show_date.trim(),
    operator: {
      company_name: config.operator.company_name?.trim() ?? '',
      name: config.operator.name.trim(),
      email: config.operator.email.trim(),
    },
    expected_specs: { ...config.expected_specs },
    expected_codecs: [...config.expected_codecs],
    preferred_codecs: [...config.preferred_codecs],
    screens: config.screens.map((screen) => {
      const row: ShowConfigData['screens'][number] = {
        id: screen.id.trim(),
        ...(screen.name?.trim() ? { name: screen.name.trim() } : {}),
        ...(screen.resolution?.trim() ? { resolution: screen.resolution.trim() } : {}),
      }
      if (perScreen && screen.expected_specs) {
        row.expected_specs = { ...screen.expected_specs }
      }
      return row
    }),
    validation_strictness: { ...config.validation_strictness },
    intake: { mode: intakeMode },
    output_specs: { mode: outputMode },
    delivery,
    filename_convention: conventionOn
      ? {
          enabled: true,
          tokens: patternTokens,
          formats: {
            version: { prefix: 'v' },
            date: 'YYYYMMDD',
            content: { allow_loop_suffix: true },
          },
        }
      : { enabled: false },
  }
}
