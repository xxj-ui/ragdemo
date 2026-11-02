/**
 * 问答页（骨架）
 * 组件分工见 02 §4.2：MessageList / CitationCard / Composer。
 * 交互契约见 04 §4.4 与 §5（citations → delta* → done | error）。
 */
import MessageList from '../components/MessageList'
import Composer from '../components/Composer'

export default function ChatPage() {
  return (
    <section className="page page--chat">
      <aside className="page__sidebar">历史（M3：conversations 列表）</aside>
      <div className="page__content">
        <MessageList />
        <Composer />
      </div>
    </section>
  )
}
