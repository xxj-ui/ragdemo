/** 轻提示（M3）：成功/失败/信息三类，3.2 s 自动消失 */
import { create } from 'zustand'

export type ToastKind = 'success' | 'error' | 'info'

export interface ToastItem {
  id: number
  kind: ToastKind
  text: string
}

interface ToastState {
  items: ToastItem[]
  push: (kind: ToastKind, text: string) => void
  dismiss: (id: number) => void
}

let seq = 0

export const useToastStore = create<ToastState>((set) => ({
  items: [],
  push: (kind, text) => {
    const id = ++seq
    set((s) => ({ items: [...s.items, { id, kind, text }] }))
    window.setTimeout(() => set((s) => ({ items: s.items.filter((t) => t.id !== id) })), 3200)
  },
  dismiss: (id) => set((s) => ({ items: s.items.filter((t) => t.id !== id) })),
}))

export const toast = {
  success: (text: string) => useToastStore.getState().push('success', text),
  error: (text: string) => useToastStore.getState().push('error', text),
  info: (text: string) => useToastStore.getState().push('info', text),
}
