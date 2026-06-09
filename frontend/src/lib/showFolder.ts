export function todayIsoDate(): string {
  const date = new Date()
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function buildShowFolderName(showName: string, showDate: string): string {
  const ymd = showDate.replace(/-/g, '')
  return `${showName.trim()}_${ymd}`
}
