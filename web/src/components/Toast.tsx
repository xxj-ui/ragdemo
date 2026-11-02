import { useState } from 'react'

export function useToast() {
  const [message, setMessage] = useState<string | null>(null)
  const show = (text: string) => {
    setMessage(text)
    window.setTimeout(() => setMessage(null), 3000)
  }
  return { message, show }
}

export default function Toast({ message }: { message: string | null }) {
  if (!message) return null
  return <div className="toast">{message}</div>
}
