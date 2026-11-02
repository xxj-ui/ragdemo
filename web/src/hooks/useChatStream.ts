import { useCallback } from 'react'
import { streamChat } from '../api/chatStream'
import { useChatStore } from '../state/chatStore'

/** 把 SSE 事件映射到 chatStore 的状态机（骨架，M3 接页面） */
export function useChatStream() {
  const store = useChatStore()
  return useCallback(
    async (question: string, signal?: AbortSignal) => {
      store.setPhase('searching')
      await streamChat(
        question,
        (e) => {
          if (e.event === 'citations') store.setCitations(e.data.items)
          else if (e.event === 'delta') store.appendDelta(e.data.text)
          else if (e.event === 'done') store.finish(e.data.conversation_id)
          else store.fail(e.data.code, e.data.message)
        },
        signal,
      )
    },
    [store],
  )
}
