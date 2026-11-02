/**
 * 输入框（骨架）：Enter 发送 / Shift+Enter 换行、≤500 字提示（SRS 8.2）。
 * 发送逻辑待 M3 接入 useChatStream；此处只保留禁用态与字数显示。
 */
import { useState } from 'react'
import { useChatStore } from '../state/chatStore'

const MAX = 500

export default function Composer() {
  const [text, setText] = useState('')
  const phase = useChatStore((s) => s.phase)
  const busy = phase === 'searching' || phase === 'streaming'
  const over = text.length > MAX

  return (
    <div className="composer">
      <textarea
        value={text}
        disabled={busy}
        placeholder="输入问题，Enter 发送，Shift+Enter 换行"
        onChange={(e) => setText(e.target.value)}
      />
      <div className="composer__bar">
        <span className={over ? 'is-error' : ''}>{text.length}/{MAX}</span>
        <button disabled={busy || over || text.trim() === ''}>发送</button>
      </div>
    </div>
  )
}
