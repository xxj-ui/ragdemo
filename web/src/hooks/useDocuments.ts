import { useCallback } from 'react'
import { useDocsStore } from '../state/docsStore'

export function useReloadDocuments() {
  const load = useDocsStore((s) => s.load)
  return useCallback(() => void load(), [load])
}
