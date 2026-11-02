import { useEffect, useState } from 'react'
import ChatPage from './pages/ChatPage'
import DocumentsPage from './pages/DocumentsPage'
import StatusPill from './components/StatusPill'

// 02 S-06：不引路由库，用 location.hash 在两个视图间切换（SRS 8.1 锚点记忆）
type View = 'chat' | 'docs'

function readView(): View {
  return window.location.hash === '#docs' ? 'docs' : 'chat'
}

export default function App() {
  const [view, setView] = useState<View>(readView())

  useEffect(() => {
    const onHash = () => setView(readView())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  return (
    <div className="app">
      <header className="app__header">
        <strong>ragdemo · 知识库问答</strong>
        <nav className="app__nav">
          <a href="#chat" className={view === 'chat' ? 'is-active' : ''}>问答</a>
          <a href="#docs" className={view === 'docs' ? 'is-active' : ''}>知识库</a>
        </nav>
        <StatusPill />
      </header>
      <main className="app__main">
        {view === 'chat' ? <ChatPage /> : <DocumentsPage />}
      </main>
    </div>
  )
}
