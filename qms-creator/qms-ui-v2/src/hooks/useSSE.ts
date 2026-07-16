import { useCallback, useRef } from 'react'
import type { SOPRequest } from '../types/questionnaire'
import { createGenerationStream } from '../api/generation'
import { useGenerationStore } from '../stores/useGenerationStore'

export function useSSE() {
  const abortRef = useRef<(() => void) | null>(null)
  const store = useGenerationStore()

  const startStream = useCallback(
    (request: SOPRequest) => {
      // Cancel previous
      abortRef.current?.()
      store.startGeneration()

      const abort = createGenerationStream(
        request,
        (event, data) => {
          if (event === 'agent_start' && data.agent) {
            store.setAgentStatus(data.agent as string, 'working')
          } else if (event === 'agent_done' && data.agent) {
            store.setAgentStatus(data.agent as string, 'done', data.content as string)
          } else if (event === 'error' && data.agent) {
            store.setAgentStatus(data.agent as string, 'error', undefined, data.error as string)
          } else if (event === 'generation_complete') {
            store.setComplete(
              (data.docx_path as string) || '',
              data.quality_report as never
            )
          }
        },
        (error) => store.setError(error),
        () => {} // onComplete handled via event
      )

      abortRef.current = abort
    },
    [store]
  )

  const cancel = useCallback(() => {
    abortRef.current?.()
    abortRef.current = null
  }, [])

  return { startStream, cancel }
}
