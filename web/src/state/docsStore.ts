/**
 * 文档域状态（02 S-07）：列表 + 上传队列
 * 上传口径：后端每次只收 1 个文件（04 Q2），前端按队列逐个 POST。
 */
import { create } from 'zustand'
import { deleteDocument, listDocuments, uploadOne } from '../api/client'
import type { DocumentItem } from '../api/client'

export type QueueStatus = 'pending' | 'uploading' | 'success' | 'failed'

export interface QueueItem {
  id: number
  name: string
  size: number
  status: QueueStatus
  message?: string
}

interface DocsState {
  items: DocumentItem[]
  loading: boolean
  queue: QueueItem[]
  busy: boolean
  load: () => Promise<void>
  uploadFiles: (files: File[]) => Promise<void>
  remove: (id: number) => Promise<void>
  clearQueue: () => void
}

let seq = 0

export const useDocsStore = create<DocsState>((set, get) => ({
  items: [],
  loading: false,
  queue: [],
  busy: false,

  async load() {
    set({ loading: true })
    try {
      set({ items: await listDocuments() })
    } finally {
      set({ loading: false })
    }
  },

  async uploadFiles(files: File[]) {
    const accepted = files.slice(0, 20)          // 单次最多 20 个，多的忽略
    const queued: QueueItem[] = accepted.map((f) => ({
      id: ++seq, name: f.name, size: f.size, status: 'pending' as const,
    }))
    set((s) => ({ queue: [...queued, ...s.queue], busy: true }))

    for (let i = 0; i < accepted.length; i += 1) {
      const item = queued[i]
      const file = accepted[i]
      set((s) => ({
        queue: s.queue.map((q) => (q.id === item.id ? { ...q, status: 'uploading' } : q)),
      }))
      try {
        const res = await uploadOne(file)
        set((s) => ({
          queue: s.queue.map((q) =>
            q.id === item.id
              ? res.status === 'success'
                ? { ...q, status: 'success', message: `${res.chunks} 个片段${res.overwritten ? ' · 已覆盖同名文档' : ''}` }
                : { ...q, status: 'failed', message: res.error?.message ?? '上传失败' }
              : q,
          ),
        }))
      } catch (err) {
        const message = (err as Error).message
        set((s) => ({
          queue: s.queue.map((q) => (q.id === item.id ? { ...q, status: 'failed', message } : q)),
        }))
      }
    }

    set({ busy: false })
    await get().load()
  },

  async remove(id: number) {
    await deleteDocument(id)
    await get().load()
  },

  clearQueue() {
    set({ queue: [] })
  },
}))

export const selectDocStats = (s: DocsState) => ({
  documentCount: s.items.length,
  chunkCount: s.items.reduce((sum, d) => sum + d.chunk_count, 0),
})
