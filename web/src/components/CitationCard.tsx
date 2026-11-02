import type { CitationItem } from '../api/client'

export default function CitationCard({ item }: { item: CitationItem }) {
  return (
    <div className="citation">
      <span className="citation__n">[{item.n}]</span>
      <span className="citation__file">{item.filename}</span>
      <span className="citation__page">{item.page ?? '全文'}</span>
      <p className="citation__snippet">{item.snippet}</p>
    </div>
  )
}
