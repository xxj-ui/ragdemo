/**
 * 助手回答的 Markdown 渲染（09 §8，SRS FR-4 / 8.2）
 *
 * 为什么需要它：知识库里的 md 文档被切分后进入参考资料，模型会把原文的
 * `**加粗**`、`1.` 列表、代码块一起复述；改造前 `.msg-text` 只有 pre-wrap，
 * 标记原样漏给用户（典型是 `**第一类：直接创建线程（基础方式） **`）。
 *
 * 三条硬约定（与 09 §8 一致，改这里要同步文档）：
 *   1. 容错优先于规范：`**xxx **` 收尾修正、空行收敛、块级元素前补空行；
 *      预处理**只作用于代码围栏以外**的段落（`**kwargs`、`int[][]`、`2*3` 不能被动）。
 *   2. 流式期也渲染：未闭合的 ``` 围栏临时补一个闭合围栏，否则后半段会被
 *      整段吞成代码块、`done` 之后又变回来（观感上像 bug）。
 *   3. `[n]` 只样式化成上标徽章、不做交互，且**跳过 code/pre 子树**；
 *      引用卡片显示哪几条仍由 MessageList 的 citedNumbers() 从原始字符串判定。
 */
import { useMemo } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'

// ----------------------------------------------------------------------
// 1. 预处理
// ----------------------------------------------------------------------

/** 列表 / 标题 / 引用 / 表格行的行首特征（用于补空行，避免粘成一段） */
const BLOCK_START = /^\s{0,3}(?:#{1,6}\s|[-*+]\s|\d{1,9}[.)]\s|>\s|\|)/
/** 代码围栏：``` 或 ~~~，至少三个 */
const FENCE_LINE = /^\s*(`{3,}|~{3,})/

/** 代码块以外的纯文本段落修正 */
function fixProse(text: string): string {
  const fixed = text
    // **xxx ** → **xxx**：右分隔符前是空白时按 CommonMark 不算加粗，不修就会露出星号
    .replace(/\*\*([^*\n]+?)\s\*\*/g, '**$1**')
    // 3 个以上空行压成 1 个
    .replace(/\n{3,}/g, '\n\n')

  // 列表/标题/引用/表格紧贴上一段时补一个空行（否则后续行会被当成段落的续行）
  const out: string[] = []
  for (const line of fixed.split('\n')) {
    const prev = out.length > 0 ? out[out.length - 1] : ''
    if (prev.trim() && BLOCK_START.test(line) && !BLOCK_START.test(prev)) out.push('')
    out.push(line)
  }
  return out.join('\n')
}

/**
 * 渲染前的文本整理：按围栏切段，代码块原样保留，只清洗围栏外的文字；
 * 流式过程中围栏未闭合时补一个闭合围栏。
 */
export function prepareMarkdown(src: string): string {
  const segs: string[] = []
  const buf: string[] = []
  let inFence = false
  let fenceChar = '`'

  const flushProse = () => {
    if (buf.length > 0) {
      segs.push(fixProse(buf.join('\n')))
      buf.length = 0
    }
  }

  for (const line of src.split('\n')) {
    const m = FENCE_LINE.exec(line)
    if (!inFence && m) {
      flushProse()
      inFence = true
      fenceChar = m[1][0]
      segs.push(line)
      continue
    }
    if (inFence) {
      segs.push(line)
      if (m && m[1][0] === fenceChar) inFence = false
      continue
    }
    buf.push(line)
  }
  flushProse()

  const out = segs.join('\n')
  return inFence ? `${out}\n${fenceChar.repeat(3)}` : out
}

// ----------------------------------------------------------------------
// 2. [n] → 上标徽章（自写 rehype 插件，不引额外依赖）
// ----------------------------------------------------------------------

/** hast 节点最小结构，避免把整棵树的类型都引进来 */
interface HastNode {
  type: string
  tagName?: string
  value?: string
  properties?: Record<string, unknown>
  children?: HastNode[]
}

const CITE_SPLIT = /(\[\d{1,2}\])/
/** 代码里的 [] 与 * 一律不能动（int[] a、a[1]、arr[i] 都是正常代码） */
const SKIP_TAGS = new Set(['code', 'pre'])

function badge(num: string): HastNode {
  return {
    type: 'element',
    tagName: 'sup',
    properties: { className: ['cite-badge'] },
    children: [{ type: 'text', value: num }],
  }
}

function walkCites(node: HastNode): void {
  if (!node.children) return
  const next: HastNode[] = []
  let changed = false

  for (const child of node.children) {
    if (child.type === 'text') {
      const parts = child.value?.split(CITE_SPLIT) ?? []
      if (parts.length > 1) {
        changed = true
        for (const part of parts) {
          if (!part) continue
          const hit = /^\[(\d{1,2})\]$/.exec(part)
          next.push(hit ? badge(hit[1]) : { type: 'text', value: part })
        }
        continue
      }
      next.push(child)
      continue
    }
    if (child.type === 'element' && child.tagName !== undefined && SKIP_TAGS.has(child.tagName)) {
      next.push(child)
      continue
    }
    walkCites(child)
    next.push(child)
  }

  if (changed) node.children = next
}

/** rehype 插件：把普通文本里的 [n] 换成 <sup class="cite-badge">n</sup> */
const rehypeCiteBadge = () => (tree: unknown) => {
  walkCites(tree as HastNode)
}

// ----------------------------------------------------------------------
// 3. 元素映射
// ----------------------------------------------------------------------

const components: Components = {
  // 外链一律新窗口打开，并带上 noopener（模型会给外部链接）
  a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
  // 表格在窄气泡里只能横向滚动，不加容器会撑破卡片
  table: ({ node: _node, ...props }) => (
    <div className="md-table-wrap">
      <table {...props} />
    </div>
  ),
  // 气泡里不放图片（09 §8：禁用图片），但要让用户知道原文这里有一张图
  img: ({ node: _node, alt }) => (
    <span className="md-img-stripped">[图片已省略{alt ? `：${alt}` : ''}]</span>
  ),
  // 页面大纲交由外层标题维护，回答里的一级/二级标题统一降级
  h1: ({ node: _node, ...props }) => <h3 {...props} />,
  h2: ({ node: _node, ...props }) => <h4 {...props} />,
}

// ----------------------------------------------------------------------
// 4. 组件
// ----------------------------------------------------------------------

export default function AnswerMarkdown({ text }: { text: string }) {
  // 每个 delta 都会走到这里；解析量级 1~10 ms，远小于 token 间隔，不做节流
  const md = useMemo(() => prepareMarkdown(text), [text])

  // 不额外包一层容器：排版与流式光标由调用方（MessageList 的 .msg-text.md）承担，
  // 光标才能紧贴在最后一个块级元素的末尾。
  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeCiteBadge]}
      components={components}
      // 模型偶尔会吐 HTML（<br>、<div>）：不渲染（默认就不渲染），也直接丢掉，
      // 免得整段标签被转义成文字铺在气泡里
      skipHtml
    >
      {md}
    </Markdown>
  )
}
