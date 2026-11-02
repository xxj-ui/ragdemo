/** 文档域状态（统计由列表现算，04 Q4） */
import { create } from 'zustand'
import { request } from '../api/client'
import type { DocumentItem } from '../api/client'

interface DocsState {
  items: DocumentItem[]
  loading: boolean
  load: () => Promise<void>
}

export const useDocsStore = create<DocsState>((set) => ({
  items: [],
  loading: false,
  async load() {
    set({ loading: true })
    try {
      const data = await request<{ items: DocumentItem[] }>('/documents')
      set({ items: data.items })
    } finally {
      set({ loading: false })
    }
  },
}))

export const selectDocStats = (s: DocsState) => ({
  documentCount: s.items.length,
  chunkCount: s.items.reduce((sum, d) => sum + d.chunk_count, 0),
})
