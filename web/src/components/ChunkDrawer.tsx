/**
 * 文档片段预览抽屉（FR-8 / API-9，只读）
 *
 * 为什么读片段而不是读原文件：rag_chunks.content 才是问答真正用到的东西，
 * 核对"为什么答错"必须看它；而且原文件可能已被清理（uploads/ 为空时仍然可用）。
 * 分页按 chunk_index 递增，与文档里的先后顺序一致。
 */
import { useCallback, useEffect, useState } from 'react'
import { listDocumentChunks } from '../api/client'
import type { DocumentChunkItem, DocumentItem } from '../api/client'
import { formatDateTime, formatSize } from '../lib/format'

const PAGE = 20

export default function ChunkDrawer({ doc, onClose }: { doc: DocumentItem | null; onClose: () => void }) {
  const [items, setItems] = useState<DocumentChunkItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (id: number, offset: number) => {
    setLoading(true)
    setError(null)
    try {
      const data = await listDocumentChunks(id, offset, PAGE)
      setTotal(data.total)
      setItems((prev) => (offset === 0 ? data.items : [...prev, ...data.items]))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!doc) return
    setItems([])
    setTotal(0)
    void load(doc.id, 0)
  }, [doc, load])

  useEffect(() => {
    if (!doc) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [doc, onClose])

  if (!doc) return null

  return (
    <div className="drawer-backdrop" role="presentation" onClick={onClose}>
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label={`${doc.filename} 的片段预览`}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="drawer-head">
          <div className="drawer-title">
            <h2 title={doc.filename}>{doc.filename}</h2>
            <p>
              {formatSize(doc.file_size)} · 共 {doc.chunk_count} 个片段 · 更新于 {formatDateTime(doc.updated_at)}
            </p>
          </div>
          <button type="button" className="btn btn-secondary drawer-close" onClick={onClose}>
            关闭
          </button>
        </header>

        <div className="drawer-body">
          {error ? <div className="drawer-error">{error}</div> : null}
          {items.length === 0 && !loading && !error ? (
            <div className="drawer-empty">这份文档没有可显示的片段。</div>
          ) : null}
          {items.map((c) => (
            <article className="chunk-item" key={c.chunk_id}>
              <div className="chunk-head">
                <span className="chunk-index">#{c.chunk_index}</span>
                {c.page ? <span className="chunk-page">第 {c.page} 页</span> : null}
              </div>
              <p className="chunk-text">{c.content}</p>
            </article>
          ))}
          {loading ? <div className="drawer-loading">加载中…</div> : null}
        </div>

        <footer className="drawer-foot">
          <span className="drawer-count">
            已显示 {items.length} / {total || doc.chunk_count}
          </span>
          {items.length < (total || doc.chunk_count) ? (
            <button
              type="button"
              className="btn btn-secondary"
              disabled={loading}
              onClick={() => void load(doc.id, items.length)}
            >
              加载更多
            </button>
          ) : null}
        </footer>
      </aside>
    </div>
  )
}
