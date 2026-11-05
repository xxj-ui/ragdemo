import { useEffect } from 'react'
import { useHealthStore } from '../state/healthStore'

const INTERVAL_MS = 30_000 // 06 A3
const WARMING_INTERVAL_MS = 3_000 // 启动预热期间加密轮询，预热一完成按钮就解锁
const BOOTSTRAP_INTERVAL_MS = 2_000 // 首次探测失败（后端刚起/PID 还没就绪）时快重试

export function useHealthPolling(): void {
  const refresh = useHealthStore((s) => s.refresh)
  const warming = useHealthStore((s) => s.warmup === 'warming')
  const state = useHealthStore((s) => s.state)
  // 预热期间 3 s；还没探到过任何结果时 2 s（否则要等 30 s 才知道预热结束了没）；就绪后 30 s
  const interval = warming
    ? WARMING_INTERVAL_MS
    : state === 'ok'
      ? INTERVAL_MS
      : BOOTSTRAP_INTERVAL_MS
  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => void refresh(), interval)
    return () => window.clearInterval(timer)
  }, [refresh, interval])
}
