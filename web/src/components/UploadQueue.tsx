/** 上传队列：逐个提交（后端每次只收 1 个文件，04 Q2） */
import { useDocsStore } from '../state/docsStore'
import type { QueueItem } from '../state/docsStore'

const STATUS_TEXT: Record<QueueItem['status'], string> = {
  pending: '等待上传',
  uploading: '解析文档…',
  success: '已完成',
  failed: '失败',
}

export default function UploadQueue() {
  const queue = useDocsStore((s) => s.queue)
  const clearQueue = useDocsStore((s) => s.clearQueue)
  if (queue.length === 0) return null

  return (
    <div className="upload-queue">
      <div className="queue-head">
        <span>上传队列</span>
        <button type="button" className="text-btn" onClick={clearQueue}>
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
                {STATUS_TEXT[q.status]}
                {q.message ? ` · ${q.message}` : ''}
              </div>
            </div>
            <div className="queue-progress">
              <div className="progress">
                <span
                  style={{
                    width:
                      q.status === 'success' ? '100%'
                        : q.status === 'uploading' ? '60%'
                        : q.status === 'failed' ? '100%'
                        : '0%',
                    background: q.status === 'failed' ? 'var(--color-destructive)' : undefined,
                  }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
