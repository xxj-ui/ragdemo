/** 对话内容：用户气泡 + 助手卡片（正文、引用来源、失败提示） */
import { useEffect, useRef } from 'react'
import { LinkIcon, SparkIcon } from './icons'
import { useChatStore } from '../state/chatStore'
import type { CitationItem } from '../api/client'
import Welcome from './Welcome'

function Citations({ items }: { items: CitationItem[] }) {
  return (
    <div className="citations">
      <div className="citations-label">
        <LinkIcon />
        <span>引用来源</span>
      </div>
      <div className="citation-list">
        {items.map((c) => (
          <div className="citation-card" key={c.n}>
            <span className="citation-n">{c.n}</span>
            <div className="citation-main">
              <div className="citation-source">
                <span className="file-name" title={c.filename}>{c.filename}</span>
              </div>
              <div className="citation-page">{c.page ?? '全文'}</div>
              <div className="citation-snippet">{c.snippet}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function MessageList() {
  const messages = useChatStore((s) => s.messages)
  const phase = useChatStore((s) => s.phase)
  const error = useChatStore((s) => s.error)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, phase, error])

  if (messages.length === 0) return <Welcome />

  return (
    <div role="log" aria-label="对话内容">
      {messages.map((m, i) => {
        const isLast = i === messages.length - 1
        if (m.role === 'user') {
          return (
            <div className="message message-user" key={i}>
              <div className="msg-body">
                <div className="msg-user-bubble">{m.content}</div>
              </div>
            </div>
          )
        }
        const searching = isLast && phase === 'searching'
        const streaming = isLast && phase === 'streaming'
        return (
          <div className="message" key={i}>
            <div className="msg-avatar" aria-hidden="true">
              <SparkIcon width={16} height={16} />
            </div>
            <div className="msg-body">
              <div className="msg-assistant-card">
                {searching ? (
                  <div className="retrieval-status">
                    <span className="spinner" aria-hidden="true" />
                    <span>正在检索知识库…</span>
                  </div>
                ) : (
                  <div className={`msg-text${streaming ? ' is-typing' : ''}`}>
                    {m.content}
                  </div>
                )}
                {m.citations.length > 0 ? <Citations items={m.citations} /> : null}
                {isLast && phase === 'failed' && error ? (
                  <div className="msg-error">
                    <strong>{error.message}</strong>
                    <span className="msg-error__hint">（{error.code}）</span>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        )
      })}
      <div ref={bottom} />
    </div>
  )
}
