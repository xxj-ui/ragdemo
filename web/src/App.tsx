import { useCallback, useEffect, useState } from 'react'
import ChatPage from './pages/ChatPage'
import DocumentsPage from './pages/DocumentsPage'
import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'
import ToastStack from './components/Toast'
import { useChatStore } from './state/chatStore'
import { useDocsStore } from './state/docsStore'

// 02 S-06：不引路由库，用 location.hash 在两个视图间切换（SRS 8.1 锚点记忆）
type View = 'chat' | 'docs'

function readView(): View {
  return window.location.hash === '#docs' ? 'docs' : 'chat'
}

export default function App() {
  const [view, setView] = useState<View>(readView)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const docCount = useDocsStore((s) => s.items.length)
  const loadDocs = useDocsStore((s) => s.load)
  const loadHistory = useChatStore((s) => s.loadHistory)

  useEffect(() => {
    const onHash = () => setView(readView())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    void loadHistory()
    void loadDocs()
  }, [loadHistory, loadDocs])

  const navigate = useCallback((next: View) => {
    setView(next)
    window.location.hash = next === 'docs' ? '#docs' : '#chat'
  }, [])

  const closeDrawer = useCallback(() => setDrawerOpen(false), [])

  return (
    <div className="app">
      <Sidebar
        view={view}
        docCount={docCount}
        onNavigate={navigate}
        onCloseDrawer={closeDrawer}
        drawerOpen={drawerOpen}
      />
      {drawerOpen ? (
        <div className="sidebar-backdrop" role="presentation" onClick={closeDrawer} />
      ) : null}

      <div className="main">
        <Topbar view={view} onOpenDrawer={() => setDrawerOpen(true)} />
        <main className="content">
          {view === 'chat' ? <ChatPage /> : <DocumentsPage />}
        </main>
      </div>

      <ToastStack />
      <p className="sr-only" aria-live="polite" />
    </div>
  )
}
