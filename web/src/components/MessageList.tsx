import { useEffect, useRef } from 'react'
import CitationCard from './CitationCard'
import { useChatStore } from '../state/chatStore'

export default function MessageList() {
  const messages = useChatStore((s) => s.messages)
  const phase = useChatStore((s) => s.phase)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, phase])

  if (messages.length === 0) {
    return <div className="empty">输入问题开始提问（M3 补欢迎页与示例问题，SRS 8.2）</div>
  }

  return (
    <div className="messages">
      {messages.map((m, i) => (
        <div key={i} className={`msg msg--${m.role}`}>
          <div className="msg__content">{m.content || (phase === 'streaming' ? '▍' : '')}</div>
          {m.citations.length > 0 && (
            <div className="msg__citations">
              {m.citations.map((c) => <CitationCard key={c.n} item={c} />)}
            </div>
          )}
        </div>
      ))}
      <div ref={bottom} />
    </div>
  )
}
