/**
 * SSE 客户端（04 §5）：用 fetch + ReadableStream 手写解析，因为 EventSource 不支持 POST body。
 * 事件形状：citations → delta* → done | error；事件 data 不套信封（全项目唯一例外）。
 */
import { ERROR_TEXT } from './client'
import type { CitationItem } from './client'

export type ChatEvent =
  | { event: 'citations'; data: { items: CitationItem[] } }
  | { event: 'delta'; data: { text: string } }
  | { event: 'done'; data: { conversation_id: number } }
  | { event: 'error'; data: { code: string; message: string } }

export async function streamChat(
  question: string,
  conversationId: number | null,
  onEvent: (e: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  // 04 §4.4 / 10.多轮会话设计 §10.1：不传 = 新建会话；传了 = 续在该会话后追加一轮
  const body = conversationId === null ? { question } : { question, conversation_id: conversationId }
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })

  // 流建立之前失败：走 HTTP 状态码 + 统一信封（04 §4.4 的关键区分）
  if (!res.ok || !res.body) {
    const body = (await res.json().catch(() => null)) as
      | { code: string; message: string }
      | null
    const code = body?.code ?? 'INTERNAL_ERROR'
    onEvent({ event: 'error', data: { code, message: ERROR_TEXT[code] ?? body?.message ?? '请求失败' } })
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // 事件以空行分隔
    let idx: number
    while ((idx = buffer.indexOf('\n\n')) >= 0 || (idx = buffer.indexOf('\r\n\r\n')) >= 0) {
      const raw = buffer.slice(0, idx)
      buffer = buffer.slice(idx + (buffer.startsWith('\r\n\r\n', idx) ? 4 : 2))
      const parsed = parseSseBlock(raw)
      if (parsed) onEvent(parsed)
    }
  }
}

function parseSseBlock(raw: string): ChatEvent | null {
  let event = ''
  const dataLines: string[] = []
  for (const line of raw.split(/\r?\n/)) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!event || dataLines.length === 0) return null
  try {
    return { event, data: JSON.parse(dataLines.join('\n')) } as ChatEvent
  } catch {
    return null
  }
}
