/** 顶栏：页面标题 + 副标题 + 服务状态（移动端左侧为抽屉按钮） */
import StatusPill from './StatusPill'
import { MenuIcon } from './icons'

interface Props {
  view: 'chat' | 'docs'
  onOpenDrawer: () => void
}

export default function Topbar({ view, onOpenDrawer }: Props) {
  const title = view === 'chat' ? '问答' : '知识库'
  const subtitle =
    view === 'chat' ? '基于知识库内容回答，并标注引用来源' : '上传文档，构建可检索的知识片段'
  return (
    <header className="topbar">
      <button type="button" className="icon-btn menu-btn" aria-label="打开侧边栏" onClick={onOpenDrawer}>
        <MenuIcon />
      </button>
      <div className="topbar-title">
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      <div className="topbar-actions">
        <StatusPill />
      </div>
    </header>
  )
}
