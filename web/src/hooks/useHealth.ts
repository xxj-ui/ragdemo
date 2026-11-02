import { useEffect } from 'react'
import { useHealthStore } from '../state/healthStore'

const INTERVAL_MS = 30_000 // 06 A3

export function useHealthPolling(): void {
  const refresh = useHealthStore((s) => s.refresh)
  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => void refresh(), INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [refresh])
}
