/** 侧边栏：品牌 / 导航 / 历史记录 / 服务状态（原型结构 1:1） */
import { useState } from 'react'
import { ChatIcon, DbIcon, HistoryIcon, PlusIcon, SparkIcon, TrashIcon } from './icons'
import ConfirmModal from './ConfirmModal'
import { useChatStore } from '../state/chatStore'
import { useHealthStore } from '../state/healthStore'

interface Props {
  view: 'chat' | 'docs'
  docCount: number
  onNavigate: (view: 'chat' | 'docs') => void
  onCloseDrawer: () => void
  drawerOpen: boolean
}

export default function Sidebar({ view, docCount, onNavigate, onCloseDrawer, drawerOpen }: Props) {
  const history = useChatStore((s) => s.history)
  const conversationId = useChatStore((s) => s.conversationId)
  const openConversation = useChatStore((s) => s.openConversation)
  const removeConversation = useChatStore((s) => s.removeConversation)
  const newChat = useChatStore((s) => s.newChat)
  const health = useHealthStore((s) => s.state)
  const [pending, setPending] = useState<{ id: number; title: string } | null>(null)
  const [error, setError] = useState('')

  const footerText =
    health === 'ok' ? '本地服务已连接' : health === 'down' ? '本地服务未连接' : '本地服务检查中'

  return (
    <aside className={`sidebar${drawerOpen ? ' is-open' : ''}`} aria-label="侧边栏">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">
          <SparkIcon width={20} height={20} />
        </div>
        <div className="brand-text">
          <strong>知问</strong>
          <span>本地知识库问答</span>
        </div>
      </div>

      <nav className="nav" aria-label="主导航">
        <button
          type="button"
          className={`nav-item${view === 'chat' ? ' is-active' : ''}`}
          aria-current={view === 'chat' ? 'page' : undefined}
          onClick={() => { onNavigate('chat'); onCloseDrawer() }}
        >
          <ChatIcon />
          <span>问答</span>
        </button>
        <button
          type="button"
          className={`nav-item${view === 'docs' ? ' is-active' : ''}`}
          aria-current={view === 'docs' ? 'page' : undefined}
          onClick={() => { onNavigate('docs'); onCloseDrawer() }}
        >
          <DbIcon />
          <span>知识库</span>
          <span className="nav-count">{docCount}</span>
        </button>
      </nav>

      <section className="history-section" aria-label="问答历史">
        <div className="section-head">
          <span>历史记录</span>
          <button
            type="button"
            className="icon-btn small"
            aria-label="新建对话"
            title="新建对话"
            onClick={() => { newChat(); onNavigate('chat'); onCloseDrawer() }}
          >
            <PlusIcon width={16} height={16} />
          </button>
        </div>

        <div className="history-list">
          {history.length === 0 ? (
            <p className="history-empty">还没有提问记录。发送第一个问题后，会出现在这里。</p>
          ) : (
            history.map((h) => (
              <div key={h.id} className={`history-item${conversationId === h.id ? ' is-active' : ''}`}>
                <button
                  type="button"
                  className="history-open"
                  title={h.title}
                  onClick={async () => {
                    try {
                      await openConversation(h.id)
                      onNavigate('chat')
                      onCloseDrawer()
                    } catch (err) {
                      setError((err as Error).message)
                    }
                  }}
                >
                  <HistoryIcon />
                  <span className="history-title">{h.title}</span>
                </button>
                <button
                  type="button"
                  className="icon-btn small history-del"
                  aria-label={`删除记录：${h.title}`}
                  title="删除这条历史"
                  onClick={() => setPending({ id: h.id, title: h.title })}
                >
                  <TrashIcon width={14} height={14} />
                </button>
              </div>
            ))
          )}
        </div>
      </section>

      <div className="sidebar-footer">
        <span className="status-dot" aria-hidden="true" />
        <span>{footerText}</span>
      </div>

      <ConfirmModal
        open={pending !== null}
        title="删除这条历史？"
        message={pending ? `「${pending.title}」的问答记录将被删除，且不可恢复。` : ''}
        confirmText="删除记录"
        onCancel={() => setPending(null)}
        onConfirm={async () => {
          if (!pending) return
          try {
            await removeConversation(pending.id)
          } catch (err) {
            setError((err as Error).message)
          } finally {
            setPending(null)
          }
        }}
      />

      <ConfirmModal
        open={error !== ''}
        title="操作失败"
        message={error}
        confirmText="知道了"
        danger={false}
        onCancel={() => setError('')}
        onConfirm={() => setError('')}
      />
    </aside>
  )
}
