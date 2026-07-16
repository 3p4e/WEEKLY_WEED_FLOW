export type AgentStatus = 'waiting' | 'working' | 'done' | 'error'

export interface AgentState {
  role: string
  label: string
  status: AgentStatus
  content?: string
  error?: string
  // KB awareness metadata
  kbSources?: {
    db1Count: number
    db2Count: number
    gapDetected?: boolean
    gapTopic?: string
  }
}

// KB context information for generation
export interface KBContextInfo {
  totalDb1Sources: number
  totalDb2Sources: number
  gapsDetected: GapDetection[]
  primarySource: 'db1' | 'db2' | 'balanced'
}

export interface GapDetection {
  section: string
  topic: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  skillFallback?: string
}

export const AGENT_PIPELINE: { role: string; label: string; primaryDb?: 'db1' | 'db2' }[] = [
  { role: 'cover', label: 'Cover Page' },
  { role: 'purpose', label: 'Purpose', primaryDb: 'db1' },
  { role: 'scope', label: 'Scope', primaryDb: 'db2' },
  { role: 'definitions', label: 'Definitions', primaryDb: 'db1' },
  { role: 'raci', label: 'RACI Matrix', primaryDb: 'db2' },
  { role: 'regulatory', label: 'Regulatory References', primaryDb: 'db1' },
  { role: 'procedure', label: 'Procedure', primaryDb: 'db2' },
  { role: 'documentation', label: 'Documentation', primaryDb: 'db1' },
  { role: 'training', label: 'Training', primaryDb: 'db2' },
  { role: 'annex', label: 'Annexes', primaryDb: 'db2' },
]
