/** 知识库页：拖拽上传 + 队列 + 文档表（统计由列表现算，04 Q4） */
import { useEffect, useRef, useState } from 'react'
import DocTable from '../components/DocTable'
import UploadQueue from '../components/UploadQueue'
import { CloudIcon } from '../components/icons'
import { useDocsStore } from '../state/docsStore'

const ACCEPT = '.pdf,.docx,.md,.txt,.xlsx,.csv'
const MAX_SIZE = 50 * 1024 * 1024

export default function DocumentsPage() {
  const uploadFiles = useDocsStore((s) => s.uploadFiles)
  const load = useDocsStore((s) => s.load)
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    void load()
  }, [load])

  async function handleFiles(list: FileList | null) {
    if (!list || list.length === 0) return
    const files = Array.from(list)

    // 明显不合法的先本地挡掉，减少无谓请求（服务端仍是最终判定）
    const valid: File[] = []
    for (const f of files) {
      const ext = `.${f.name.split('.').pop()?.toLowerCase() ?? ''}`
      if (!ACCEPT.split(',').includes(ext)) {
        useDocsStore.setState((s) => ({
          queue: [
            { id: Date.now() + Math.random(), name: f.name, size: f.size, status: 'failed' as const, message: '不支持的文件类型' },
            ...s.queue,
          ],
        }))
        continue
      }
      if (f.size === 0) {
        useDocsStore.setState((s) => ({
          queue: [
            { id: Date.now() + Math.random(), name: f.name, size: 0, status: 'failed' as const, message: '文件为空' },
            ...s.queue,
          ],
        }))
        continue
      }
      if (f.size > MAX_SIZE) {
        useDocsStore.setState((s) => ({
          queue: [
            { id: Date.now() + Math.random(), name: f.name, size: f.size, status: 'failed' as const, message: '超过 50 MB' },
            ...s.queue,
          ],
        }))
        continue
      }
      valid.push(f)
    }
    if (valid.length > 0) await uploadFiles(valid)
  }

  return (
    <section className="docs-scroll" aria-label="知识库">
      <div className="docs-inner">
        <div
          className={`dropzone${dragging ? ' is-dragging' : ''}`}
          role="button"
          tabIndex={0}
          aria-label="选择或拖拽文档上传"
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click()
          }}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            void handleFiles(e.dataTransfer.files)
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            multiple
            hidden
            onChange={(e) => {
              void handleFiles(e.target.files)
              e.target.value = ''
            }}
          />
          <div className="dropzone-icon" aria-hidden="true">
            <CloudIcon />
          </div>
          <p className="dropzone-title">
            拖拽文件到此处，或<span className="link">点击选择</span>
          </p>
          <p className="dropzone-hint">
            支持 PDF、Word、Markdown、TXT、Excel、CSV · 单文件 ≤ 50 MB · 每次上传 1 个文件（可连续选择）
          </p>
        </div>

        <UploadQueue />
        <DocTable onUploadClick={() => inputRef.current?.click()} />
      </div>
    </section>
  )
}
