import api from './client'
import type { RAGSearchResponse } from '../types/api'

export interface SearchKnowledgeOptions {
  query: string
  archive?: 'db1' | 'db2' | 'both'
  topK?: number
  sopName?: string  // For gap detection context
}

export async function searchKnowledge(
  query: string,
  archive?: 'db1' | 'db2' | 'both',
  topK: number = 5,
  sopName?: string
): Promise<RAGSearchResponse> {
  const { data } = await api.post('/api/rag-query', {
    query,
    archive: archive || 'both',
    top_k: topK,
    sop_name: sopName,
  })
  return data
}

// Enhanced search with full options object
export async function searchKnowledgeAdvanced(
  options: SearchKnowledgeOptions
): Promise<RAGSearchResponse> {
  const { data } = await api.post('/api/rag-query', {
    query: options.query,
    archive: options.archive || 'both',
    top_k: options.topK || 5,
    sop_name: options.sopName,
  })
  return data
}
