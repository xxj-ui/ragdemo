/**
 * 上传队列（骨架）：每次只提交 1 个文件（04 Q2），失败原因取 error.code 映射。
 * 阶段进度无法提供，只显示「处理中」（04 Q5）。
 */
export default function UploadQueue() {
  return (
    <div className="upload">
      <input type="file" multiple disabled />
      <p className="hint">支持 pdf / docx / md / txt / xlsx / csv，单文件 ≤ 50 MB</p>
    </div>
  )
}
