import { create } from 'zustand'
import type { QMSDocument } from '../types/document'
import type { StatsResponse } from '../types/api'

interface DocumentState {
  documents: QMSDocument[]
  stats: StatsResponse | null
  filter: { department: string; status: string; search: string }
  viewMode: 'grid' | 'list'
  setDocuments: (docs: QMSDocument[]) => void
  setStats: (stats: StatsResponse) => void
  setFilter: (key: string, value: string) => void
  setViewMode: (mode: 'grid' | 'list') => void
}

export const useDocumentStore = create<DocumentState>((set) => ({
  documents: [],
  stats: null,
  filter: { department: '', status: '', search: '' },
  viewMode: 'grid',
  setDocuments: (documents) => set({ documents }),
  setStats: (stats) => set({ stats }),
  setFilter: (key, value) => set((s) => ({ filter: { ...s.filter, [key]: value } })),
  setViewMode: (viewMode) => set({ viewMode }),
}))
