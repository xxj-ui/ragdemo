/**
 * 知识库页（骨架）
 * 组件分工见 02 §4.2：UploadQueue / DocTable / ConfirmModal。
 * 统计（F-08）由 GET /api/documents 现算（04 Q4），不额外请求。
 */
import DocTable from '../components/DocTable'
import UploadQueue from '../components/UploadQueue'

export default function DocumentsPage() {
  return (
    <section className="page page--docs">
      <UploadQueue />
      <DocTable />
    </section>
  )
}
