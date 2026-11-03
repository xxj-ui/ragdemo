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

/**
 * 引用卡片的副标题：优先从片段头部解析出真实定位（时间 / 原题），
 * 解析不到再退回 page。语料的每一行都是一条新闻，行首常带
 * `2023-07-28 10:14`、`07-28 16:15`、`[ 2023-07-21 00：45 ]`、`原标题：…` 这几类前缀，
 * 直接把 `page` 显示成"全文"没有信息量。
 */
export function citationMeta(snippet: string, page: string | null): string {
  const s = snippet.trim()
  const bracket = s.match(/^\[\s*(\d{4}-\d{2}-\d{2})\s*([\d:：]{4,8})?\s*\]/)
  if (bracket) return `${bracket[1]}${bracket[2] ? ' ' + bracket[2].replace(/：/g, ':') : ''}`
  const dated = s.match(/^(\d{4}-\d{2}-\d{2})\s*([\d:：]{4,8})?/)
  if (dated) return `${dated[1]}${dated[2] ? ' ' + dated[2].replace(/：/g, ':') : ''}`
  const short = s.match(/^(\d{2}-\d{2})\s*(\d{2}:\d{2})/)
  if (short) return `${short[1]} ${short[2]}`
  const title = s.match(/^原标题[:：]\s*([^。！？]{2,26})/)
  if (title) return title[1].trim()
  // 只有真正有页号的文件（PDF / Word）才显示页码；解析不到定位就返回空，
  // 由调用方整行隐藏——"全文"三个字没有信息量，只会让卡片看起来一样。
  return page && /^\d+$/.test(page.trim()) ? `第 ${page.trim()} 页` : ''
}

/** 摘要正文：去掉行首的时间戳 / `，正文：` 标记，让用户直接读到内容 */
export function citationBody(snippet: string): string {
  return snippet
    .replace(/^\[\s*[^\]]{4,32}\]\s*/, '')
    .replace(/^\d{4}-\d{2}-\d{2}\s*[\d:：]{0,8}\s*/, '')
    .replace(/^\d{2}-\d{2}\s*\d{2}:\d{2}\s*/, '')
    .replace(/^[^，]{0,40}，正文：/, '')
    .replace(/^原标题[:：]\s*/, '')
    .trim()
}
