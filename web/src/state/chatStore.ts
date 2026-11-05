/**
 * 会话域状态（02 S-07：一个域一个 store）
 * 状态机（04 §5.2）：idle → searching → streaming → done | failed
 * 事件序列：citations（0/1） → delta（1~N） → done | error
 */
import { create } from 'zustand'
import { getConversation, listConversations } from '../api/client'
import type { CitationItem, ConversationListItem } from '../api/client'
import { streamChat } from '../api/chatStream'

export type ChatPhase = 'idle' | 'searching' | 'streaming' | 'done' | 'failed'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  citations: CitationItem[]
}

interface ChatState {
  phase: ChatPhase
  messages: ChatMessage[]
  error: { code: string; message: string } | null
  conversationId: number | null
  history: ConversationListItem[]
  historyLoading: boolean
  ask: (question: string) => Promise<void>
  loadHistory: () => Promise<void>
  openConversation: (id: number) => Promise<void>
  removeConversation: (id: number) => Promise<void>
  newChat: () => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  phase: 'idle',
  messages: [],
  error: null,
  conversationId: null,
  history: [],
  historyLoading: false,

  async ask(question: string) {
    const clean = question.trim()
    if (!clean || get().phase === 'searching' || get().phase === 'streaming') return

    // 多轮：带上当前会话 id（打开历史会话后继续提问 = 追加到同一会话，FR-9）
    set((s) => ({
      phase: 'searching',
      error: null,
      messages: [...s.messages, { role: 'user', content: clean, citations: [] },
                 { role: 'assistant', content: '', citations: [] }],
    }))

    const patchLast = (fn: (m: ChatMessage) => ChatMessage) =>
      set((s) => {
        const messages = [...s.messages]
        const i = messages.length - 1
        if (i < 0) return { messages }
        messages[i] = fn(messages[i])
        return { messages }
      })

    try {
      // 引用先到达但先不落位：SSE 顺序是 citations → delta* → done，
      // 若立刻渲染，用户会先看到一排引用卡片、正文还是空的。
      // 这里只暂存，等回答流结束再挂到消息上（"先答完、再给来源"）。
      let pendingCitations: CitationItem[] = []
      await streamChat(clean, get().conversationId, (ev) => {
        if (ev.event === 'citations') {
          pendingCitations = ev.data.items
          // 不切到 streaming：让"正在检索知识库…"一直显示到第一个字到达
        } else if (ev.event === 'delta') {
          patchLast((m) => ({ ...m, content: m.content + ev.data.text }))
          set({ phase: 'streaming' })
        } else if (ev.event === 'done') {
          set({ phase: 'done', conversationId: ev.data.conversation_id })
        } else if (ev.event === 'error') {
          // 会话被删除后继续提问：清掉 id，下次提问回到"新建会话"，用户不会卡在这条会话上
          const gone = ev.data.code === 'CONVERSATION_NOT_FOUND'
          set({ phase: 'failed', error: { code: ev.data.code, message: ev.data.message },
                ...(gone ? { conversationId: null } : {}) })
        }
      })
      if (pendingCitations.length > 0) {
        patchLast((m) => ({ ...m, citations: pendingCitations }))
      }
      // 流可能在没有 done / error 的情况下就结束（代理掐断、后端被重启、网络抖动）：
      // 那时 phase 会停在 streaming，界面就是一个永远闪烁的光标 + 空白卡片。
      // 这里做收口：有内容按完成处理，没内容按失败处理，至少给用户一个明确状态。
      const phaseAfter = get().phase
      if (phaseAfter === 'streaming' || phaseAfter === 'searching') {
        const last = get().messages[get().messages.length - 1]
        if (!last || !last.content.trim()) {
          set({ phase: 'failed', error: { code: 'STREAM_INTERRUPTED', message: '回答中断，请重试' } })
        } else {
          set({ phase: 'done' })
        }
      }
      if (get().phase !== 'failed') void get().loadHistory()
    } catch (err) {
      set({ phase: 'failed', error: { code: 'INTERNAL_ERROR', message: (err as Error).message } })
    }
  },

  async loadHistory() {
    set({ historyLoading: true })
    try {
      const items = await listConversations(50, 0)
      set({ history: items })
    } catch {
      /* 侧边栏历史失败不打断主流程 */
    } finally {
      set({ historyLoading: false })
    }
  },

  async openConversation(id: number) {
    const detail = await getConversation(id)
    // 打开历史会话后可直接续聊（不再只读回放）
    set({
      phase: 'done',
      error: null,
      conversationId: detail.id,
      messages: detail.messages.map((m) => ({
        role: m.role,
        content: m.content,
        citations: m.citations ?? [],
      })),
    })
  },

  async removeConversation(id: number) {
    set((s) => ({ history: s.history.filter((h) => h.id !== id) }))
    if (get().conversationId === id) get().newChat()
  },

  newChat() {
    set({ phase: 'idle', messages: [], error: null, conversationId: null })
  },
}))
