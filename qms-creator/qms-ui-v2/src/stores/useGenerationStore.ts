import { create } from 'zustand'
import type { AgentState, AgentStatus, KBContextInfo, GapDetection } from '../types/generation'
import { AGENT_PIPELINE } from '../types/generation'
import type { QualityReport } from '../types/api'

interface GenerationState {
  isGenerating: boolean
  agents: AgentState[]
  qualityReport: QualityReport | null
  docxPath: string | null
  error: string | null
  // KB awareness state
  kbContext: KBContextInfo | null
  startGeneration: () => void
  setAgentStatus: (role: string, status: AgentStatus, content?: string, error?: string) => void
  setAgentKBSources: (role: string, db1Count: number, db2Count: number, gapDetected?: boolean, gapTopic?: string) => void
  addGapDetection: (gap: GapDetection) => void
  setComplete: (docxPath: string, qualityReport?: QualityReport) => void
  setError: (error: string) => void
  reset: () => void
}

const makeInitialAgents = (): AgentState[] =>
  AGENT_PIPELINE.map((a) => ({ ...a, status: 'waiting' as AgentStatus }))

const makeInitialKBContext = (): KBContextInfo => ({
  totalDb1Sources: 0,
  totalDb2Sources: 0,
  gapsDetected: [],
  primarySource: 'balanced',
})

export const useGenerationStore = create<GenerationState>((set) => ({
  isGenerating: false,
  agents: makeInitialAgents(),
  qualityReport: null,
  docxPath: null,
  error: null,
  kbContext: null,
  startGeneration: () =>
    set({
      isGenerating: true,
      agents: makeInitialAgents(),
      qualityReport: null,
      docxPath: null,
      error: null,
      kbContext: makeInitialKBContext(),
    }),
  setAgentStatus: (role, status, content, error) =>
    set((s) => ({
      agents: s.agents.map((a) => (a.role === role ? { ...a, status, content, error } : a)),
    })),
  setAgentKBSources: (role, db1Count, db2Count, gapDetected, gapTopic) =>
    set((s) => {
      const newAgents = s.agents.map((a) =>
        a.role === role
          ? { ...a, kbSources: { db1Count, db2Count, gapDetected, gapTopic } }
          : a
      )
      // Update totals in kbContext
      const totalDb1 = newAgents.reduce((sum, a) => sum + (a.kbSources?.db1Count || 0), 0)
      const totalDb2 = newAgents.reduce((sum, a) => sum + (a.kbSources?.db2Count || 0), 0)
      const primarySource = totalDb1 > totalDb2 * 1.5 ? 'db1' : totalDb2 > totalDb1 * 1.5 ? 'db2' : 'balanced'
      return {
        agents: newAgents,
        kbContext: s.kbContext ? {
          ...s.kbContext,
          totalDb1Sources: totalDb1,
          totalDb2Sources: totalDb2,
          primarySource,
        } : null,
      }
    }),
  addGapDetection: (gap) =>
    set((s) => ({
      kbContext: s.kbContext ? {
        ...s.kbContext,
        gapsDetected: [...s.kbContext.gapsDetected, gap],
      } : null,
    })),
  setComplete: (docxPath, qualityReport) =>
    set({ isGenerating: false, docxPath, qualityReport: qualityReport || null }),
  setError: (error) => set({ isGenerating: false, error }),
  reset: () => set({
    isGenerating: false,
    agents: makeInitialAgents(),
    qualityReport: null,
    docxPath: null,
    error: null,
    kbContext: null,
  }),
}))
