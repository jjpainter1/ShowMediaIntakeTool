const API_BASE =
  import.meta.env.VITE_API_BASE ??
  (import.meta.env.DEV ? '' : 'http://127.0.0.1:8000')

export type HealthResponse = {
  status: string
  phase?: number
  ffprobe_available: boolean
  user_data_root: string
}

export type RecentShow = {
  path: string
  show_name: string
  last_used: string
  dashboard_view: string | null
}

export type ShowSummary = {
  path: string
  show_name: string
  preset: string | null
  schema_version: number | null
}

export type DashboardViewMode = 'cards' | 'compact'

export type ParsedFile = {
  screen_prefix: string
  slug: string
  version: number
  date: string
  extension: string
  is_loop: boolean
  original_name: string
}

export type MediaFile = {
  filename: string
  size_bytes: number
}

export type ScreenFileDetail = {
  filename: string
  file_path: string
  size_bytes: number
  location: string
  specs: {
    width: number | null
    height: number | null
    framerate: number | null
    codec: string | null
    probe_succeeded: boolean
  }
  spec_status: {
    resolution: SpecStatus
    codec: SpecStatus
    fps: SpecStatus
  }
  warnings: string[]
  failures: string[]
}

export type ScreenSnapshot = {
  screen_id: string
  screen_name: string
  resolution: string | null
  parsed_files: ParsedFile[]
  unparsed_files: string[]
  files: MediaFile[]
  file_count: number
  slug_count: number
}

export type DashboardSnapshot = {
  show_root: string
  show_name: string
  show_date: string
  screens: Record<string, ScreenSnapshot>
  special_folders: Record<string, string[]>
  review_files: string[]
  stale_folders: { name: string; path: string; file_count: number }[]
  multi_version_slugs: { label: string; versions: ParsedFile[] }[]
  last_delivery: string | null
  days_until_show: number | null
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const STALE_BACKEND_MESSAGE =
  'Dashboard API is unavailable. Restart the Python backend with ' +
  'python -m uvicorn backend.main:app --reload --port 8000 ' +
  '(an older process may still be running without Phase 2 routes).'

export function formatDashboardError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404 && (err.message === 'Not Found' || err.message.includes('Not Found'))) {
      return STALE_BACKEND_MESSAGE
    }
    return err.message
  }
  if (err instanceof Error) {
    return err.message
  }
  return 'Failed to load dashboard'
}

async function parseError(response: Response): Promise<string> {
  const text = await response.text()
  if (!text) {
    return response.statusText
  }
  try {
    const body = JSON.parse(text) as { detail?: string | { msg: string }[] }
    if (typeof body.detail === 'string') {
      return body.detail
    }
    if (Array.isArray(body.detail)) {
      return body.detail.map((item) => item.msg).join('; ')
    }
    return text
  } catch {
    return text
  }
}

async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

export function fetchHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/api/health')
}

export function fetchRecentShows(): Promise<RecentShow[]> {
  return apiRequest<RecentShow[]>('/api/recent-shows')
}

export function loadShow(path: string): Promise<ShowSummary> {
  return apiRequest<ShowSummary>(`/api/shows/load?path=${encodeURIComponent(path)}`)
}

export function fetchScreenFiles(
  path: string,
  screenId: string,
): Promise<{ path: string; screen_id: string; files: ScreenFileDetail[] }> {
  const params = new URLSearchParams({ path, screen_id: screenId })
  return apiRequest(`/api/shows/screen-files?${params}`)
}

export function fetchDashboard(path: string): Promise<DashboardSnapshot> {
  return apiRequest<DashboardSnapshot>(
    `/api/shows/dashboard?path=${encodeURIComponent(path)}`,
  )
}

export function patchDashboardView(
  path: string,
  view: DashboardViewMode,
): Promise<{ path: string; dashboard_view: string }> {
  return apiRequest('/api/recent-shows/dashboard-view', {
    method: 'PATCH',
    body: JSON.stringify({ path, view }),
  })
}

export function fetchDeliveryLog(path: string): Promise<{ path: string; lines: string[] }> {
  return apiRequest(`/api/shows/delivery-log?path=${encodeURIComponent(path)}`)
}

export type DeliveryHistoryEntry = {
  timestamp: string
  source_path: string
  copied: number
  review: number
  skip: number
  notes: string | null
  intake_log_path: string | null
}

export function fetchDeliveryHistory(
  path: string,
): Promise<{ path: string; entries: DeliveryHistoryEntry[] }> {
  return apiRequest(`/api/shows/delivery-history?path=${encodeURIComponent(path)}`)
}

export function fetchIntakeLogContent(
  showPath: string,
  logPath: string,
): Promise<{ log_path: string; content: string }> {
  const params = new URLSearchParams({ path: showPath, log_path: logPath })
  return apiRequest(`/api/shows/intake-log?${params.toString()}`)
}

export function migrateShow(path: string): Promise<{ backup_path: string; message: string }> {
  return apiRequest(`/api/shows/migrate?path=${encodeURIComponent(path)}`, {
    method: 'POST',
  })
}

export function createShow(
  parentPath: string,
  showName: string,
  showDate: string,
): Promise<ShowSummary> {
  return apiRequest<ShowSummary>('/api/shows/create', {
    method: 'POST',
    body: JSON.stringify({
      parent_path: parentPath,
      show_name: showName,
      show_date: showDate,
    }),
  })
}

// --- Intake Delivery ---

export type IntakeAction =
  | 'COPY'
  | 'COPY_WITH_WARNING'
  | 'ROUTE_TO_REVIEW'
  | 'SKIP_IDENTICAL'

export type SpecStatus = 'default' | 'warn' | 'fail'

export type IntakeFilePlan = {
  filename: string
  source_path: string
  parsed: {
    kind: 'full' | 'partial' | 'none'
    parsed?: ParsedFile
    screen_prefix?: string
    original?: string
    problems?: string[]
  }
  specs: {
    width: number | null
    height: number | null
    framerate: number | null
    codec: string | null
    probe_succeeded: boolean
    probe_error: string | null
  } | null
  spec_status: {
    resolution: SpecStatus
    codec: SpecStatus
    fps: SpecStatus
  }
  size_bytes: number
  destination_path: string
  destination_label: string
  action: IntakeAction
  warnings: string[]
  failures: string[]
  version_conflict: {
    existing_versions: ParsedFile[]
    incoming_version: number
  } | null
}

export type IntakeStaleFolder = {
  name: string
  path: string
  file_count: number
}

export type IntakeScanResult = {
  show_path: string
  source_path: string
  plans: IntakeFilePlan[]
  stale_folders: IntakeStaleFolder[]
}

export type IntakeExecuteResult = {
  show_path: string
  source_path: string
  result: {
    copied: string[]
    skipped: string[]
    routed_to_review: string[]
    copy_failures: { source_path: string; reason: string }[]
  }
  intake_log_path: string
}

export type IntakeScanProgress = {
  current: number
  total: number
  filename: string
}

export type IntakeCopyProgress = IntakeScanProgress & {
  status: 'done' | 'failed' | 'skipped'
}

function wsOrigin(): string {
  const base = API_BASE || window.location.origin
  const url = new URL(base, window.location.origin)
  const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${url.host}`
}

class IntakeWebSocketError extends Error {
  constructor(message = 'Could not connect to intake service') {
    super(message)
    this.name = 'IntakeWebSocketError'
  }
}

const STALE_INTAKE_MESSAGE =
  'Intake API unavailable. Restart the backend: .\\scripts\\start-backend.ps1 ' +
  '(an older process may still be on port 8000 without Phase 4 routes).'

export function formatIntakeError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404) {
      return STALE_INTAKE_MESSAGE
    }
    return err.message
  }
  if (err instanceof IntakeWebSocketError) {
    return err.message
  }
  if (err instanceof Error) {
    return err.message
  }
  return 'Intake operation failed'
}

function intakeWebSocket<TComplete>(
  path: string,
  payload: object,
  onEvent?: (data: Record<string, unknown>) => void,
): Promise<TComplete> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`${wsOrigin()}${path}`)
    let settled = false

    const fail = (err: Error) => {
      if (settled) {
        return
      }
      settled = true
      reject(err)
      ws.close()
    }

    ws.onopen = () => {
      ws.send(JSON.stringify(payload))
    }

    ws.onmessage = (event) => {
      let data: Record<string, unknown>
      try {
        data = JSON.parse(String(event.data)) as Record<string, unknown>
      } catch {
        fail(new Error('Invalid WebSocket response'))
        return
      }

      if (data.type === 'error') {
        fail(new Error(String(data.message ?? 'Intake operation failed')))
        return
      }

      if (data.type === 'progress') {
        onEvent?.(data)
        return
      }

      if (data.type === 'complete') {
        if (settled) {
          return
        }
        settled = true
        const { type: _type, ...result } = data
        resolve(result as TComplete)
        ws.close()
      }
    }

    ws.onerror = () => {
      fail(new IntakeWebSocketError())
    }

    ws.onclose = (event) => {
      if (!settled && !event.wasClean) {
        fail(new IntakeWebSocketError())
      }
    }
  })
}

export async function scanIntake(
  showPath: string,
  sourcePath: string,
  onProgress?: (progress: IntakeScanProgress) => void,
): Promise<IntakeScanResult> {
  try {
    return await intakeWebSocket<IntakeScanResult>(
      '/api/intake/scan/ws',
      { show_path: showPath, source_path: sourcePath },
      (data) => {
        if (data.type === 'progress') {
          onProgress?.({
            current: Number(data.current ?? 0),
            total: Number(data.total ?? 0),
            filename: String(data.filename ?? ''),
          })
        }
      },
    )
  } catch (err) {
    if (!(err instanceof IntakeWebSocketError)) {
      throw err
    }
    const result = await apiRequest<IntakeScanResult>('/api/intake/scan', {
      method: 'POST',
      body: JSON.stringify({ show_path: showPath, source_path: sourcePath }),
    })
    onProgress?.({
      current: result.plans.length,
      total: result.plans.length,
      filename: '',
    })
    return result
  }
}

export async function executeIntake(
  showPath: string,
  sourcePath: string,
  plans: IntakeFilePlan[],
  staleFolders: IntakeStaleFolder[],
  onProgress?: (progress: IntakeCopyProgress) => void,
): Promise<IntakeExecuteResult> {
  try {
    return await intakeWebSocket<IntakeExecuteResult>(
      '/api/intake/execute/ws',
      {
        show_path: showPath,
        source_path: sourcePath,
        plans,
        stale_folders: staleFolders,
      },
      (data) => {
        if (data.type === 'progress') {
          onProgress?.({
            current: Number(data.current ?? 0),
            total: Number(data.total ?? 0),
            filename: String(data.filename ?? ''),
            status: (data.status as IntakeCopyProgress['status']) ?? 'done',
          })
        }
      },
    )
  } catch (err) {
    if (!(err instanceof IntakeWebSocketError)) {
      throw err
    }
    const result = await apiRequest<IntakeExecuteResult>('/api/intake/execute', {
      method: 'POST',
      body: JSON.stringify({
        show_path: showPath,
        source_path: sourcePath,
        plans,
        stale_folders: staleFolders,
      }),
    })
    const actionable = plans.filter((plan) => plan.action !== 'SKIP_IDENTICAL')
    onProgress?.({
      current: actionable.length,
      total: actionable.length,
      filename: '',
      status: 'done',
    })
    return result
  }
}

export function pickFolderFromServer(title = 'Select folder'): Promise<string | null> {
  const params = new URLSearchParams({ title })
  return apiRequest<{ cancelled: boolean; path: string | null }>(
    `/api/system/pick-folder?${params}`,
  ).then((data) => (data.cancelled || !data.path ? null : data.path))
}

export function openIntakeLog(logPath: string): Promise<{ opened: boolean; log_path: string }> {
  return apiRequest('/api/intake/open-log', {
    method: 'POST',
    body: JSON.stringify({ log_path: logPath }),
  })
}

// --- Config Editor ---

export type ShowConfigData = {
  schema_version: number
  preset: string
  show_name: string
  show_date: string
  operator: { name: string; email: string }
  expected_specs: {
    framerate: number | null
    color_space: string | null
    color_range: string | null
    audio_sample_rate: number | null
    audio_channels: number | null
  }
  expected_codecs: string[]
  preferred_codecs: string[]
  screens: { id: string; name?: string; resolution?: string }[]
  validation_strictness: Record<string, string>
}

export type PresetData = {
  preset_name: string
  preset_description: string
  expected_specs: ShowConfigData['expected_specs']
  expected_codecs: string[]
  preferred_codecs: string[]
  validation_strictness: Record<string, string>
  source: string
}

export function fetchShowConfig(path: string): Promise<ShowConfigData> {
  return apiRequest<ShowConfigData>(`/api/shows/config?path=${encodeURIComponent(path)}`)
}

export function saveShowConfig(
  path: string,
  config: ShowConfigData,
): Promise<{ path: string; config_path: string }> {
  return apiRequest('/api/shows/config', {
    method: 'PUT',
    body: JSON.stringify({ path, config }),
  })
}

export function openShowConfig(path: string): Promise<{ opened: boolean; config_path: string }> {
  return apiRequest('/api/shows/open-config', {
    method: 'POST',
    body: JSON.stringify({ path }),
  })
}

export function fetchPresets(): Promise<{ builtin: PresetData[]; custom: PresetData[] }> {
  return apiRequest('/api/presets')
}

export function applyPreset(
  presetName: string,
  config: ShowConfigData,
): Promise<{ config: ShowConfigData }> {
  return apiRequest('/api/presets/apply', {
    method: 'POST',
    body: JSON.stringify({ preset_name: presetName, config }),
  })
}

export function saveCustomPreset(
  presetName: string,
  config: ShowConfigData,
): Promise<{ preset_name: string; path: string }> {
  return apiRequest('/api/presets/custom', {
    method: 'POST',
    body: JSON.stringify({ preset_name: presetName, config }),
  })
}

export function importPresetFile(filePath: string): Promise<PresetData> {
  return apiRequest('/api/presets/import', {
    method: 'POST',
    body: JSON.stringify({ path: filePath }),
  })
}

export function fetchCodecIdentifiers(): Promise<{ identifiers: string[] }> {
  return apiRequest('/api/codecs')
}

export function openPathInExplorer(path: string): Promise<{ opened: boolean; path: string }> {
  return apiRequest('/api/system/open-path', {
    method: 'POST',
    body: JSON.stringify({ path }),
  })
}

export function pickFileFromServer(
  title = 'Select file',
  filetypes = 'JSON files|*.json|All files|*.*',
): Promise<string | null> {
  const params = new URLSearchParams({ title, filetypes })
  return apiRequest<{ cancelled: boolean; path: string | null }>(
    `/api/system/pick-file?${params}`,
  ).then((data) => (data.cancelled || !data.path ? null : data.path))
}

const STALE_CONFIG_MESSAGE =
  'Config API unavailable. Restart the backend: .\\scripts\\start-backend.ps1 ' +
  '(an older process may still be on port 8000 without Phase 5 routes).'

export function formatConfigError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404) {
      return STALE_CONFIG_MESSAGE
    }
    return err.message
  }
  if (err instanceof Error) {
    return err.message
  }
  return 'Config operation failed'
}
