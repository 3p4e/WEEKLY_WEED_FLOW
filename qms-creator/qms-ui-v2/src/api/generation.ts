import api from './client'
import type { SOPRequest } from '../types/questionnaire'

export async function submitQuestionnaire(request: SOPRequest) {
  const { data } = await api.post('/submit-questionnaire', request)
  return data
}

export async function generateDirect(request: SOPRequest) {
  const { data } = await api.post('/generate', request)
  return data
}

export function createGenerationStream(
  request: SOPRequest,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  onError: (error: string) => void,
  onComplete: () => void
): () => void {
  // Use fetch + ReadableStream for SSE since EventSource only supports GET
  const controller = new AbortController()

  fetch('/api/generate-stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        onError(`HTTP ${response.status}`)
        return
      }
      const reader = response.body?.getReader()
      if (!reader) {
        onError('No response body')
        return
      }
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            const eventType = line.slice(7).trim()
            // Next line should be data
            const dataLine = lines[lines.indexOf(line) + 1]
            if (dataLine?.startsWith('data: ')) {
              try {
                const data = JSON.parse(dataLine.slice(6))
                onEvent(eventType, data)
                if (eventType === 'generation_complete') onComplete()
              } catch {
                // skip malformed data
              }
            }
          } else if (line.startsWith('data: ')) {
            try {
              const parsed = JSON.parse(line.slice(6))
              const eventType = parsed.event || 'message'
              const payload = parsed.data || parsed
              onEvent(eventType, payload)
              if (eventType === 'generation_complete') onComplete()
            } catch {
              // skip
            }
          }
        }
      }
      onComplete()
    })
    .catch((err) => {
      if (err.name !== 'AbortError') onError(err.message)
    })

  return () => controller.abort()
}
