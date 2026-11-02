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
  /** 打开的是历史会话（只读回放；继续提问会新建会话，后端一期一问一答） */
  replaying: boolean
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
  replaying: false,
  history: [],
  historyLoading: false,

  async ask(question: string) {
    const clean = question.trim()
    if (!clean || get().phase === 'searching' || get().phase === 'streaming') return

    set((s) => ({
      phase: 'searching',
      error: null,
      replaying: false,
      conversationId: null,
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
      await streamChat(clean, (ev) => {
        if (ev.event === 'citations') {
          patchLast((m) => ({ ...m, citations: ev.data.items }))
          set({ phase: 'streaming' })
        } else if (ev.event === 'delta') {
          patchLast((m) => ({ ...m, content: m.content + ev.data.text }))
          set({ phase: 'streaming' })
        } else if (ev.event === 'done') {
          set({ phase: 'done', conversationId: ev.data.conversation_id })
        } else if (ev.event === 'error') {
          set({ phase: 'failed', error: { code: ev.data.code, message: ev.data.message } })
        }
      })
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
    set({
      phase: 'done',
      error: null,
      conversationId: detail.id,
      replaying: true,
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
    set({ phase: 'idle', messages: [], error: null, conversationId: null, replaying: false })
  },
}))
