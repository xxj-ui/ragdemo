/** 展示层格式化：大小 / 时间 / 文件类型 */

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/** 后端给的是 ISO 带 +08:00；今天显示"今天 HH:mm"，否则"M月D日" */
export function formatTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const now = new Date()
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  if (sameDay) return `今天 ${hm}`
  if (d.getFullYear() === now.getFullYear()) return `${d.getMonth() + 1}月${d.getDate()}日`
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 文件类型 → 图标配色类（对应原型 .file-pdf / .file-doc / .file-md / .file-txt / .file-xls） */
export function fileKindClass(fileType: string): string {
  switch (fileType.toLowerCase()) {
    case 'pdf':
      return 'file-pdf'
    case 'docx':
      return 'file-doc'
    case 'md':
      return 'file-md'
    case 'xlsx':
    case 'csv':
      return 'file-xls'
    default:
      return 'file-txt'
  }
}

export const FILE_TYPE_LABEL: Record<string, string> = {
  pdf: 'PDF',
  docx: 'Word',
  md: 'Markdown',
  txt: 'Text',
  xlsx: 'Excel',
  csv: 'CSV',
}
