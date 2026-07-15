export interface ApiError {
  detail: string
}

export interface StatsResponse {
  total_documents: number
  departments: Record<string, number>
  document_types: Record<string, number>
  status_counts: Record<string, number>
}

export interface HierarchyNode {
  code: string
  title: string
  department: string
  status: string
  children?: HierarchyNode[]
}

export interface GenerateStreamEvent {
  event: 'agent_start' | 'agent_done' | 'generation_complete' | 'error'
  data: {
    agent?: string
    content?: string
    docx_path?: string
    quality_report?: QualityReport
    error?: string
  }
}

export interface QualityReport {
  overall_score: number
  section_scores: Record<string, number>
  compliance_checks: ComplianceCheck[]
  recommendations: string[]
}

export interface ComplianceCheck {
  rule: string
  passed: boolean
  details: string
}

// KB Metadata types for enriched RAG results
export interface PassageMetadata {
  category: string
  quality: number
  source_authority: 'official_regulatory' | 'operational_example'
  reg_align?: number
  year?: string
}

export interface GapInfo {
  topic: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  description: string
  skill_fallback?: string
}

export interface RAGResult {
  text: string
  tags: string[]
  score: number
  id: string
  // KB Metadata (computed at query time)
  metadata?: PassageMetadata
}

export interface RAGSearchResponse {
  db1_results: RAGResult[]
  db2_results: RAGResult[]
  // Gap detection info (if query relates to a gap topic)
  gap_info?: GapInfo
  // Query metadata
  query?: string
  db_weights?: {
    db1: number
    db2: number
  }
}
