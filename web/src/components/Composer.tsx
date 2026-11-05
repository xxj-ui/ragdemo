/** 输入框：Enter 发送、Shift+Enter 换行、500 字上限（SRS 8.2）；模型预热期间禁用 */
import { useRef, useState } from 'react'
import { SendIcon } from './icons'
import { useChatStore } from '../state/chatStore'
import { useHealthStore } from '../state/healthStore'

const MAX = 500

export default function Composer() {
  const [text, setText] = useState('')
  const phase = useChatStore((s) => s.phase)
  const ask = useChatStore((s) => s.ask)
  // 启动预热期间（M8）禁用发送：否则用户会等 100 秒还以为卡死
  const warming = useHealthStore((s) => s.warmup === 'warming')
  const ref = useRef<HTMLTextAreaElement>(null)
  const busy = phase === 'searching' || phase === 'streaming'
  const over = text.length > MAX
  const canSend = !busy && !warming && !over && text.trim() !== ''

  function submit() {
    if (!canSend) return
    const question = text
    setText('')
    if (ref.current) ref.current.style.height = 'auto'
    void ask(question)
  }

  return (
    <div className="composer-wrap">
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <textarea
          ref={ref}
          rows={1}
          maxLength={MAX + 50}
          value={text}
          placeholder={warming ? '模型预热中，请稍候…' : '输入问题，向知识库提问…'}
          aria-label="输入问题"
          onChange={(e) => {
            setText(e.target.value)
            const el = e.target
            el.style.height = 'auto'
            el.style.height = `${Math.min(el.scrollHeight, 160)}px`
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              submit()
            }
          }}
        />
        <div className="composer-bar">
          <span className="composer-hint">
            {warming ? '模型预热中，完成后可提问' : 'Enter 发送 · Shift + Enter 换行'}
          </span>
          <div className="composer-actions">
            <span className={`char-count${over ? ' is-error' : ''}`}>
              {text.length} / {MAX}
            </span>
            <button type="submit" className="send-btn" aria-label="发送问题" disabled={!canSend}>
              <SendIcon />
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
