type OpenDialogOptions = {
  directory?: boolean
  multiple?: boolean
  title?: string
}

export async function open(
  _options?: OpenDialogOptions,
): Promise<string | string[] | null> {
  throw new Error('Dialog plugin is not available outside Tauri')
}
