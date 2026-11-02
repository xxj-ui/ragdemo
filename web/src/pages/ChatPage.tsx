/** 问答页：消息区 + 输入区 */
import MessageList from '../components/MessageList'
import Composer from '../components/Composer'

export default function ChatPage() {
  return (
    <section className="view view-chat is-active" aria-label="问答">
      <div className="chat-scroll">
        <div className="chat-inner">
          <MessageList />
        </div>
      </div>
      <Composer />
    </section>
  )
}
