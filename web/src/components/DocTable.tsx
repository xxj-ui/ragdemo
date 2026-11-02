import { useEffect } from 'react'
import { useDocsStore, selectDocStats } from '../state/docsStore'

export default function DocTable() {
  const { items, loading, load } = useDocsStore()
  const stats = useDocsStore(selectDocStats)

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="docs">
      <p className="hint">
        共 {stats.documentCount} 份文档 / {stats.chunkCount} 个片段（F-08，由列表现算）
        {loading && ' · 加载中…'}
      </p>
      {items.length === 0 ? (
        <div className="empty">知识库为空，先上传文档（空状态引导待 M3）</div>
      ) : (
        <table>
          <thead>
            <tr><th>文件名</th><th>类型</th><th>大小</th><th>片段数</th><th>最近更新</th><th>操作</th></tr>
          </thead>
          <tbody>
            {items.map((d) => (
              <tr key={d.id}>
                <td>{d.filename}</td>
                <td>{d.file_type}</td>
                <td>{(d.file_size / 1024).toFixed(0)} KB</td>
                <td>{d.chunk_count}</td>
                <td>{d.updated_at}</td>
                <td><button disabled>删除</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
