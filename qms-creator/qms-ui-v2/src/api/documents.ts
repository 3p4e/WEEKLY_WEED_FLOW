import api from './client'
import type { StatsResponse, HierarchyNode } from '../types/api'
import type { QMSDocument } from '../types/document'

export async function getStats(): Promise<StatsResponse> {
  const { data } = await api.get('/api/stats')
  return data
}

export async function getHierarchy(): Promise<HierarchyNode[]> {
  const { data } = await api.get('/api/hierarchy')
  return data
}

export async function getDocuments(): Promise<QMSDocument[]> {
  const { data } = await api.get('/api/documents')
  return data
}

export async function getDocument(code: string): Promise<QMSDocument> {
  const { data } = await api.get(`/api/documents/${code}`)
  return data
}
