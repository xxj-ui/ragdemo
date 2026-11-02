/** 二次确认弹窗（删除文档 / 删除历史） */
import { useEffect } from 'react'
import { AlertIcon, TrashIcon } from './icons'

interface Props {
  open: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmModal({
  open, title, message, confirmText = '删除', cancelText = '取消', danger = true, onConfirm, onCancel,
}: Props) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onCancel])

  if (!open) return null
  return (
    <div className="modal-backdrop is-visible" role="presentation" onClick={onCancel}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modalTitle"
        aria-describedby="modalMessage"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={`modal-icon${danger ? '' : ' is-info'}`} aria-hidden="true">
          {danger ? <TrashIcon width={20} height={20} /> : <AlertIcon width={20} height={20} />}
        </div>
        <h2 id="modalTitle">{title}</h2>
        <p id="modalMessage">{message}</p>
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onCancel}>
            {cancelText}
          </button>
          <button
            type="button"
            className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`}
            onClick={onConfirm}
            autoFocus
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
