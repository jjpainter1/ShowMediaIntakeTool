import { open } from '@tauri-apps/plugin-dialog'

export async function pickFolderTauri(title: string): Promise<string | null> {
  const selected = await open({
    directory: true,
    multiple: false,
    title,
  })
  if (selected === null) {
    return null
  }
  return typeof selected === 'string' ? selected : selected[0] ?? null
}
