/**
 * 健康状态（03 A3 已定）：30 s 轮询；请求失败连续 2 次 → 不可用；
 * degraded 立即展示（不计失败次数）；任一次恢复即回就绪。
 */
import { create } from 'zustand'
import { request } from '../api/client'
import type { HealthData } from '../api/client'

export type ServiceState = 'ok' | 'degraded' | 'down' | 'unknown'

interface HealthStore {
  state: ServiceState
  model: HealthData['embedding_model'] | 'unknown'
  llmKey: HealthData['llm_key'] | 'unknown'
  failures: number
  refresh: () => Promise<void>
}

export const useHealthStore = create<HealthStore>((set, get) => ({
  state: 'unknown',
  model: 'unknown',
  llmKey: 'unknown',
  failures: 0,
  async refresh() {
    try {
      const data = await request<HealthData>('/health')
      set({
        state: data.status === 'ok' ? 'ok' : 'degraded',
        model: data.embedding_model,
        llmKey: data.llm_key,
        failures: 0,
      })
    } catch {
      const failures = get().failures + 1
      set({ failures, state: failures >= 2 ? 'down' : get().state })
    }
  },
}))
