/** 文档表格 + 空状态；删除走二次确认 */
import { useState } from 'react'
import ConfirmModal from './ConfirmModal'
import { FileEmptyIcon, FileIcon, TrashIcon, UploadIcon } from './icons'
import { useDocsStore, selectDocStats } from '../state/docsStore'
import { toast } from '../state/toastStore'
import { FILE_TYPE_LABEL, fileKindClass, formatDateTime, formatSize } from '../lib/format'
import type { DocumentItem } from '../api/client'

export default function DocTable({ onUploadClick }: { onUploadClick: () => void }) {
  const items = useDocsStore((s) => s.items)
  const loading = useDocsStore((s) => s.loading)
  const remove = useDocsStore((s) => s.remove)
  const { documentCount, chunkCount } = useDocsStore(selectDocStats)
  const [pending, setPending] = useState<DocumentItem | null>(null)

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h2>
            全部文档 <span className="count-badge">{documentCount}</span>
          </h2>
          <p className="panel-sub">共 {chunkCount} 个知识片段{loading ? ' · 加载中…' : ''}</p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={onUploadClick}>
          <UploadIcon />
          上传文档
        </button>
      </div>

      {items.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon" aria-hidden="true">
            <FileEmptyIcon />
          </div>
          <h3>还没有文档</h3>
          <p>上传第一份资料，开始构建你的知识库。</p>
          <button type="button" className="btn btn-primary" onClick={onUploadClick}>
            上传文档
          </button>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="doc-table">
            <thead>
              <tr>
                <th scope="col">文件名</th>
                <th scope="col">类型</th>
                <th scope="col">大小</th>
                <th scope="col">片段数</th>
                <th scope="col">最近更新</th>
                <th scope="col"><span className="sr-only">操作</span></th>
              </tr>
            </thead>
            <tbody>
              {items.map((d) => (
                <tr key={d.id}>
                  <td>
                    <div className="file-cell">
                      <span className={`file-icon ${fileKindClass(d.file_type)}`} aria-hidden="true">
                        <FileIcon />
                      </span>
                      <div>
                        <div className="file-name" title={d.filename}>{d.filename}</div>
                        <div className="file-sub">{FILE_TYPE_LABEL[d.file_type] ?? d.file_type}</div>
                      </div>
                    </div>
                  </td>
                  <td><span className="type-badge">{d.file_type.toUpperCase()}</span></td>
                  <td className="cell-muted">{formatSize(d.file_size)}</td>
                  <td className="cell-muted">{d.chunk_count}</td>
                  <td className="cell-muted">{formatDateTime(d.updated_at)}</td>
                  <td className="cell-actions">
                    <button
                      type="button"
                      className="icon-btn small"
                      aria-label={`删除 ${d.filename}`}
                      title="删除"
                      onClick={() => setPending(d)}
                    >
                      <TrashIcon />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmModal
        open={pending !== null}
        title="删除这份文档？"
        message={pending ? `「${pending.filename}」的 ${pending.chunk_count} 个知识片段和原始文件将一并删除，且不可恢复。` : ''}
        onCancel={() => setPending(null)}
        onConfirm={async () => {
          if (!pending) return
          const name = pending.filename
          try {
            await remove(pending.id)
            toast.success(`已删除「${name}」`)
          } catch (err) {
            toast.error((err as Error).message)
          } finally {
            setPending(null)
          }
        }}
      />
    </div>
  )
}
