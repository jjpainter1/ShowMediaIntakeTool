import { isTauri } from '@tauri-apps/api/core'
import { pickFolderFromServer } from './api'

export async function pickFolder(title = 'Select show folder'): Promise<string | null> {
  if (isTauri()) {
    const { pickFolderTauri } = await import('./folderPicker.tauri')
    return pickFolderTauri(title)
  }

  return pickFolderFromServer(title)
}

/** Pick a delivery source folder (standard Windows folder dialog). */
export async function pickDeliverySource(
  title = 'Select delivery source folder',
): Promise<string | null> {
  if (isTauri()) {
    const { pickFolderTauri } = await import('./folderPicker.tauri')
    return pickFolderTauri(title)
  }
  return pickFolderFromServer(title)
}
