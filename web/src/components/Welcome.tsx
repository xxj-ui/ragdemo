/** 空态欢迎页：知识库规模 + 示例问题（有历史时用历史标题当示例） */
import { SparkIcon } from './icons'
import { useChatStore } from '../state/chatStore'
import { useDocsStore, selectDocStats } from '../state/docsStore'

const DEFAULT_EXAMPLES = ['这份文档讲了什么？', '有哪些关键步骤？', '总结一下核心结论']

export default function Welcome() {
  const { documentCount, chunkCount } = useDocsStore(selectDocStats)
  const ask = useChatStore((s) => s.ask)
  const history = useChatStore((s) => s.history)
  const examples = history.length > 0 ? history.slice(0, 4).map((h) => h.title) : DEFAULT_EXAMPLES

  return (
    <div className="welcome">
      <div className="welcome-mark" aria-hidden="true">
        <SparkIcon width={26} height={26} />
      </div>
      <h2>有什么可以帮你？</h2>
      <p>回答只基于你的知识库内容，并标注引用来源。找不到依据时会明确告诉你。</p>
      <p className="welcome-meta">
        {documentCount > 0
          ? `已收录 ${documentCount} 份文档 · ${chunkCount} 个知识片段`
          : '知识库还是空的 · 先去「知识库」上传文档'}
      </p>
      <div className="examples">
        {examples.map((q) => (
          <button key={q} type="button" className="example-chip" onClick={() => void ask(q)}>
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}
