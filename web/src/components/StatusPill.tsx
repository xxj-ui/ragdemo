import { useHealthStore } from '../state/healthStore'

const TEXT = { ok: '就绪', degraded: '降级', down: '服务不可用', unknown: '检查中' } as const

export default function StatusPill() {
  const state = useHealthStore((s) => s.state)
  const model = useHealthStore((s) => s.model)
  const label = model === 'loading' ? '模型加载中' : TEXT[state]
  return <span className={`pill pill--${state}`}>{label}</span>
}
