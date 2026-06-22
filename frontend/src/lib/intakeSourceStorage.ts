const KEY_PREFIX = 'intake_source:'

export function getIntakeSourcePath(showPath: string): string {
  try {
    return localStorage.getItem(`${KEY_PREFIX}${showPath}`) ?? ''
  } catch {
    return ''
  }
}

export function saveIntakeSourcePath(showPath: string, sourcePath: string): void {
  try {
    const trimmed = sourcePath.trim()
    const key = `${KEY_PREFIX}${showPath}`
    if (trimmed) {
      localStorage.setItem(key, trimmed)
    } else {
      localStorage.removeItem(key)
    }
  } catch {
    // localStorage may be unavailable
  }
}
