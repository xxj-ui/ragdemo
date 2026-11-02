export interface ConfirmModalProps {
  open: boolean
  title: string
  description: string
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmModal({ open, title, description, onConfirm, onCancel }: ConfirmModalProps) {
  if (!open) return null
  return (
    <div className="modal" role="dialog" aria-modal="true">
      <div className="modal__box">
        <h3>{title}</h3>
        <p>{description}</p>
        <div className="modal__actions">
          <button onClick={onCancel}>取消</button>
          <button className="danger" onClick={onConfirm}>确认</button>
        </div>
      </div>
    </div>
  )
}
