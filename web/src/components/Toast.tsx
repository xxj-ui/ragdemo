/** 轻提示堆栈 */
import { useToastStore } from '../state/toastStore'

export default function ToastStack() {
  const items = useToastStore((s) => s.items)
  const dismiss = useToastStore((s) => s.dismiss)
  if (items.length === 0) return null
  return (
    <div className="toast-stack" aria-live="polite">
      {items.map((t) => (
        <div key={t.id} className={`toast toast-${t.kind}`} role="status" onClick={() => dismiss(t.id)}>
          <span>{t.text}</span>
        </div>
      ))}
    </div>
  )
}
