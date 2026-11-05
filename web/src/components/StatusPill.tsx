/** 服务状态胶囊（06 A3：30 s 轮询、连续 2 次失败降级） */
import { useEffect } from 'react'
import { useHealthStore } from '../state/healthStore'
import { useHealthPolling } from '../hooks/useHealth'

const LABEL: Record<string, string> = {
  ok: '知识库就绪',
  degraded: '部分能力不可用',
  down: '服务不可用',
  unknown: '检查中…',
}

export default function StatusPill() {
  useHealthPolling()
  const { state, model, warmup, llmKey } = useHealthStore()
  const warming = warmup === 'warming'
  const label = warming ? '模型预热中…' : LABEL[state]
  const detail = warming
    ? '正在后台加载向量模型与检索索引，预热完成后即可提问'
    : state === 'ok'
      ? '数据库、向量模型与问答服务均正常'
      : [
          model === 'loading' ? '向量模型加载中' : '',
          model === 'failed' ? '向量模型不可用' : '',
          llmKey === 'missing' ? '未配置大模型 Key' : '',
          state === 'down' ? '无法连接本地服务' : '',
        ]
          .filter(Boolean)
          .join(' · ')

  useEffect(() => {
    // 让读屏用户也能得到状态变化提示
    document.body.dataset.serviceState = state
  }, [state])

  return (
    <span className={`status-pill is-${warming ? 'warming' : state}`} title={detail || label}>
      <span className="status-dot" aria-hidden="true" />
      <span>{label ?? LABEL.unknown}</span>
    </span>
  )
}
