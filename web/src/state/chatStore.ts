/**
 * 会话域状态（02 S-07：Zustand，一个域一个 store）
 * 状态机：idle → searching → streaming → done | failed
 */
import { create } from 'zustand'
import type { CitationItem } from '../api/client'

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
  currentConversationId: number | null
  setPhase: (p: ChatPhase) => void
  appendDelta: (text: string) => void
  setCitations: (items: CitationItem[]) => void
  finish: (conversationId: number) => void
  fail: (code: string, message: string) => void
  reset: () => void
}

export const useChatStore = create<ChatState>((set) => ({
  phase: 'idle',
  messages: [],
  error: null,
  currentConversationId: null,
  setPhase: (phase) => set({ phase }),
  appendDelta: (text) =>
    set((s) => {
      const messages = [...s.messages]
      const last = messages[messages.length - 1]
      if (last && last.role === 'assistant') {
        messages[messages.length - 1] = { ...last, content: last.content + text }
      }
      return { messages, phase: 'streaming' }
    }),
  setCitations: (items) =>
    set((s) => {
      const messages = [...s.messages]
      const last = messages[messages.length - 1]
      if (last && last.role === 'assistant') messages[messages.length - 1] = { ...last, citations: items }
      return { messages }
    }),
  finish: (conversationId) => set({ phase: 'done', error: null, currentConversationId: conversationId }),
  fail: (code, message) => set({ phase: 'failed', error: { code, message } }),
  reset: () => set({ phase: 'idle', messages: [], error: null, currentConversationId: null }),
}))
