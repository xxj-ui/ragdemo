/**
 * 对话内容：用户气泡 + 助手卡片（正文、引用来源、失败提示）
 *
 * 引用展示口径（feat/citation-cards）：
 *   1. 默认只展示答案里真正引用到的编号（正文里的 [n]）；其余折叠成一个可展开入口，
 *      避免"列 5 条、实际只用 2 条"让用户误判检索质量。
 *   2. 卡片可点击，展开后取消两行截断，把后端给的 100 字摘要完整露出来。
 *   3. 副标题不再是没信息量的"全文"，而是从片段头部解析出的时间 / 原题。
 */
import { useEffect, useRef, useState } from 'react'
import { LinkIcon, SparkIcon } from './icons'
import { useChatStore } from '../state/chatStore'
import type { CitationItem } from '../api/client'
import { citationBody, citationMeta } from '../lib/format'
import Welcome from './Welcome'

/** 答案里出现的 [n] 编号集合；模型一个都没标时回退为"全部展示" */
function citedNumbers(answer: string): Set<number> {
  const out = new Set<number>()
  for (const m of answer.matchAll(/\[(\d{1,2})\]/g)) out.add(Number(m[1]))
  return out
}

function CitationCard({
  item,
  expanded,
  onToggle,
  dimmed,
}: {
  item: CitationItem
  expanded: boolean
  onToggle: () => void
  dimmed?: boolean
}) {
  const meta = citationMeta(item.snippet, item.page)
  return (
    <button
      type="button"
      className={`citation-card${dimmed ? ' is-uncited' : ''}${expanded ? ' is-expanded' : ''}`}
      onClick={onToggle}
      aria-expanded={expanded}
      title={expanded ? '点击收起' : '点击展开完整摘要'}
    >
      <span className="citation-n">{item.n}</span>
      <div className="citation-main">
        <div className="citation-source">
          <span className="file-name" title={item.filename}>{item.filename}</span>
        </div>
        {meta ? <div className="citation-page">{meta}</div> : null}
        <div className={`citation-snippet${expanded ? ' is-expanded' : ''}`}>
          {citationBody(item.snippet)}
        </div>
      </div>
    </button>
  )
}

function Citations({
  items,
  answer,
  expanded,
  toggle,
}: {
  items: CitationItem[]
  answer: string
  expanded: Record<number, boolean>
  toggle: (n: number) => void
}) {
  const [showUncited, setShowUncited] = useState(false)
  const cited = citedNumbers(answer)
  const hasMarks = cited.size > 0

  // 模型一个编号都没标（典型就是"根据已有资料无法回答"）时，默认不铺开这些卡片——
  // 有 5 条检索结果却没被答案用上，直接展示只会让人以为"检索到了却答错"。
  // 想排查仍然点得开。
  const used = hasMarks ? items.filter((c) => cited.has(c.n)) : []
  const rest = hasMarks ? items.filter((c) => !cited.has(c.n)) : items

  return (
    <div className="citations">
      {used.length > 0 ? (
        <div className="citations-label">
          <LinkIcon />
          <span>引用来源</span>
          <span className="citations-count">答案引用了 {used.length}/{items.length} 条</span>
        </div>
      ) : null}
      {(used.length > 0 || showUncited) ? (
        <div className="citation-list">
          {used.map((c) => (
            <CitationCard
              key={c.n}
              item={c}
              expanded={!!expanded[c.n]}
              onToggle={() => toggle(c.n)}
            />
          ))}
          {showUncited
            ? rest.map((c) => (
                <CitationCard
                  key={c.n}
                  item={c}
                  dimmed
                  expanded={!!expanded[c.n]}
                  onToggle={() => toggle(c.n)}
                />
              ))
            : null}
        </div>
      ) : null}
      {rest.length > 0 ? (
        <button type="button" className="citation-toggle" onClick={() => setShowUncited((v) => !v)}>
          {showUncited
            ? '收起'
            : used.length === 0
              ? `查看 ${rest.length} 条检索片段`
              : `另有 ${rest.length} 条未被答案引用`}
        </button>
      ) : null}
    </div>
  )
}

export default function MessageList() {
  const messages = useChatStore((s) => s.messages)
  const phase = useChatStore((s) => s.phase)
  const error = useChatStore((s) => s.error)
  const bottom = useRef<HTMLDivElement>(null)
  // 展开状态按「消息序号-引用编号」记，跨消息不会串
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const toggle = (msgIndex: number, n: number) =>
    setExpanded((prev) => {
      const key = `${msgIndex}-${n}`
      return { ...prev, [key]: !prev[key] }
    })

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
                {m.citations.length > 0 ? (
                  <Citations
                    items={m.citations}
                    answer={m.content}
                    expanded={Object.fromEntries(
                      Object.entries(expanded)
                        .filter(([k]) => k.startsWith(`${i}-`))
                        .map(([k, v]) => [Number(k.slice(`${i}-`.length)), v]),
                    )}
                    toggle={(n) => toggle(i, n)}
                  />
                ) : null}
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
