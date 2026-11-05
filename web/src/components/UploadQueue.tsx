/**
 * 上传队列：逐个提交（后端每次只收 1 个文件，04 Q2）
 *
 * 进度口径（2026-11 裁决）：不展示进度百分比、上传过程中不提供取消。
 * 上传期间只有一个状态文案「上传中…」，直到请求返回、列表刷新为止。
 * 这里不渲染进度条——服务端耗时在解析/切分/向量化，前端拿不到真实进度，
 * 画一根假进度条只会误导用户。
 */
import { useDocsStore } from '../state/docsStore'
import type { QueueItem } from '../state/docsStore'

const STATUS_TEXT: Record<QueueItem['status'], string> = {
  pending: '等待上传',
  uploading: '上传中…',
  success: '已完成',
  failed: '失败',
}

export default function UploadQueue() {
  const queue = useDocsStore((s) => s.queue)
  const busy = useDocsStore((s) => s.busy)
  const clearQueue = useDocsStore((s) => s.clearQueue)
  if (queue.length === 0) return null

  return (
    <div className="upload-queue">
      <div className="queue-head">
        <span>{busy ? '上传中，完成前不可取消' : '上传队列'}</span>
        {/* 上传中禁用「清除」：清列表不等于取消请求，请求仍会在后台跑完并入库 */}
        <button type="button" className="text-btn" onClick={clearQueue} disabled={busy}>
          清除
        </button>
      </div>
      <div className="queue-body">
        {queue.map((q) => (
          <div
            key={q.id}
            className={`queue-row${q.status === 'failed' ? ' is-failed' : ''}${q.status === 'success' ? ' is-success' : ''}`}
          >
            <div className="queue-file">
              <div className="queue-name" title={q.name}>{q.name}</div>
              <div className="queue-status">
                <span className={`queue-dot is-${q.status}`} aria-hidden="true" />
                {STATUS_TEXT[q.status]}
                {q.message ? ` · ${q.message}` : ''}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
