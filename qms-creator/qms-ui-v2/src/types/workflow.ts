/**
 * Type definitions for the 9-Agent Interactive Workflow
 */

export type AgentNumber = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9

export type AgentPhase =
  | 'metadata'
  | 'questionnaire_intro'
  | 'questionnaire_procedure'
  | 'automated_compliance'
  | 'automated_raci'
  | 'qa_review'
  | 'formatting'
  | 'questionnaire_annex'
  | 'annex_formatting'
  | 'complete'

export type AgentStatus = 'pending' | 'in_progress' | 'completed' | 'skipped'

export interface AgentInfo {
  number: AgentNumber
  name: string
  description: string
  icon: string
  phase: AgentPhase
  requiresUserInteraction: boolean
  status: AgentStatus
}

// ═══════════════════════════════════════════════════════════════
// AGENT 1: METADATA
// ═══════════════════════════════════════════════════════════════

export interface AnnexSpecification {
  id: string
  title: string
  shortDescription: string
  intendedPurpose: string
}

export interface MetadataFormData {
  sopTitle: string
  shortDescription: string
  department: string[]
  documentCode?: string // Auto-generated
  annexes: AnnexSpecification[]
  // EU GMP Compliance Classification
  gmpRiskClassification?: 'gmp_critical' | 'gmp_relevant' | 'administrative'
  dataIntegrityRisk?: 'high' | 'medium' | 'low'
}

// ═══════════════════════════════════════════════════════════════
// AGENT 2/3/8: QUESTIONNAIRES
// ═══════════════════════════════════════════════════════════════

export type QuestionType =
  | 'single_choice'
  | 'multiple_choice'
  | 'text'
  | 'number'
  | 'scale'

export interface QuestionOption {
  value: string
  label: string
  description?: string
  recommended?: boolean
  sourceDb?: 'DB1' | 'DB2'
  sourceRef?: string
}

export interface Question {
  id: string
  questionNumber: number
  totalQuestions: number
  text: string
  type: QuestionType
  options: QuestionOption[]
  ragContext?: RAGContext
  required: boolean
  helpText?: string
}

export interface RAGContext {
  db1Results: RAGResult[]
  db2Results: RAGResult[]
}

export interface RAGResult {
  text: string
  source: string
  score: number
}

export interface QuestionnaireResponse {
  questionId: string
  answer: string | string[] // Single or multiple answers
  timestamp: Date
}

// ═══════════════════════════════════════════════════════════════
// AGENT 4/5: AUTOMATED PROCESSING
// ═══════════════════════════════════════════════════════════════

export interface ProcessingStatus {
  agent: AgentNumber
  phase: string
  message: string
  progress: number // 0-100
  contentPreview?: string
}

export interface GeneratedContent {
  sections: Record<string, string> // section number -> content
  metadata: {
    generatedAt: Date
    wordCount: number
    sectionsGenerated: string[]
  }
}

export interface RACIMatrix {
  activities: RACIActivity[]
  roles: string[]
}

export interface RACIActivity {
  activity: string
  assignments: Record<string, 'R' | 'A' | 'C' | 'I'> // role -> RACI value
}

// ═══════════════════════════════════════════════════════════════
// AGENT 6: QA REVIEW
// ═══════════════════════════════════════════════════════════════

export interface QAReviewReport {
  overallScore: number // 0-100
  scores: {
    regulatoryCompliance: number
    internalConsistency: number
    completeness: number
  }
  recommendations: Recommendation[]
  gaps: ComplianceGap[]
}

export interface Recommendation {
  id: string
  section: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  title: string
  description: string
  options: RecommendationOption[]
  autoApply?: boolean
}

export interface RecommendationOption {
  value: string
  label: string
  description: string
  impact: string
}

export interface ComplianceGap {
  section: string
  requirement: string
  source: string
  severity: 'critical' | 'high' | 'medium'
}

export interface QASelection {
  recommendationId: string
  selectedOption: string
}

// ═══════════════════════════════════════════════════════════════
// AGENT 7/9: DOCUMENT GENERATION
// ═══════════════════════════════════════════════════════════════

export interface DocumentGenerationStatus {
  agent: AgentNumber
  phase: string
  progress: number // 0-100
  currentStep: string
  stepsCompleted: string[]
  estimatedTimeRemaining?: number // seconds
}

export interface GeneratedDocument {
  path: string
  filename: string
  size: number
  generatedAt: Date
  downloadUrl: string
  previewUrl?: string
}

// ═══════════════════════════════════════════════════════════════
// WORKFLOW STATE
// ═══════════════════════════════════════════════════════════════

export interface WorkflowState {
  // Current state
  currentAgent: AgentNumber
  currentPhase: AgentPhase
  agents: AgentInfo[]

  // Agent 1: Metadata
  metadata: MetadataFormData | null
  workflowId: string | null

  // Agent 2: Introduction Questionnaire
  introQuestions: Question[]
  introAnswers: QuestionnaireResponse[]

  // Agent 3: Procedure Questionnaire
  procedureQuestions: Question[]
  procedureAnswers: QuestionnaireResponse[]

  // Agent 4/5: Automated Processing
  complianceContent: GeneratedContent | null
  raciMatrix: RACIMatrix | null
  processingStatus: ProcessingStatus | null

  // Agent 6: QA Review
  qaReview: QAReviewReport | null
  qaSelections: QASelection[]

  // Agent 7: Document Formatting
  sopDocument: GeneratedDocument | null
  formattingStatus: DocumentGenerationStatus | null

  // Agent 8/9: Annexes
  annexQuestionnaires: Record<string, {
    questions: Question[]
    answers: QuestionnaireResponse[]
  }>
  annexDocuments: GeneratedDocument[]

  // Workflow control
  isProcessing: boolean
  error: string | null
  canProceed: boolean
}

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

export const AGENT_DEFINITIONS: Omit<AgentInfo, 'status'>[] = [
  {
    number: 1,
    name: 'Metadata Orchestrator',
    description: 'Collect SOP metadata and specifications',
    icon: '📝',
    phase: 'metadata',
    requiresUserInteraction: true,
  },
  {
    number: 2,
    name: 'Introduction Architect',
    description: 'Generate introduction, objectives, scope, regulatory requirements',
    icon: '📄',
    phase: 'questionnaire_intro',
    requiresUserInteraction: true,
  },
  {
    number: 3,
    name: 'Procedure Engineer',
    description: 'Develop core procedure and documentation sections',
    icon: '⚙️',
    phase: 'questionnaire_procedure',
    requiresUserInteraction: true,
  },
  {
    number: 4,
    name: 'Compliance Integrator',
    description: 'Complete associated documents, definitions, training',
    icon: '🔍',
    phase: 'automated_compliance',
    requiresUserInteraction: false,
  },
  {
    number: 5,
    name: 'RACI Specialist',
    description: 'Generate RACI matrix and responsibility assignments',
    icon: '👥',
    phase: 'automated_raci',
    requiresUserInteraction: false,
  },
  {
    number: 6,
    name: 'Quality Assembler',
    description: 'QA review and final content validation',
    icon: '✅',
    phase: 'qa_review',
    requiresUserInteraction: true,
  },
  {
    number: 7,
    name: 'Document Formatter',
    description: 'Format and generate professional DOCX document',
    icon: '📑',
    phase: 'formatting',
    requiresUserInteraction: false,
  },
  {
    number: 8,
    name: 'Annex Content Creator',
    description: 'Develop annex forms, templates, and flowcharts',
    icon: '📋',
    phase: 'questionnaire_annex',
    requiresUserInteraction: true,
  },
  {
    number: 9,
    name: 'Annex Formatter',
    description: 'Format and generate annex DOCX files',
    icon: '📎',
    phase: 'annex_formatting',
    requiresUserInteraction: false,
  },
]

export const DEPARTMENT_OPTIONS = [
  { value: 'qa', label: 'Quality Assurance', icon: '✅' },
  { value: 'qc', label: 'Quality Control', icon: '🔬' },
  { value: 'production', label: 'Production', icon: '🏭' },
  { value: 'cultivation', label: 'Cultivation', icon: '🌿' },
  { value: 'extraction', label: 'Extraction', icon: '⚗️' },
  { value: 'packaging', label: 'Packaging', icon: '📦' },
  { value: 'warehouse', label: 'Warehouse', icon: '🏢' },
  { value: 'engineering', label: 'Engineering', icon: '🔧' },
]

// ═══════════════════════════════════════════════════════════════
// EU GMP RISK CLASSIFICATION MAPPING
// ═══════════════════════════════════════════════════════════════

/**
 * Map department to default GMP risk classification
 * Per ICH Q9 Quality Risk Management and EU GMP Chapter 1
 */
export const DEPARTMENT_GMP_RISK_MAP: Record<string, {
  gmpRisk: 'gmp_critical' | 'gmp_relevant' | 'administrative'
  dataIntegrityRisk: 'high' | 'medium' | 'low'
  euGmpChapter: string
}> = {
  qa: {
    gmpRisk: 'gmp_critical',
    dataIntegrityRisk: 'high',
    euGmpChapter: 'EU GMP Chapter 1, 6',
  },
  qc: {
    gmpRisk: 'gmp_critical',
    dataIntegrityRisk: 'high',
    euGmpChapter: 'EU GMP Chapter 6',
  },
  production: {
    gmpRisk: 'gmp_critical',
    dataIntegrityRisk: 'high',
    euGmpChapter: 'EU GMP Chapter 5',
  },
  cultivation: {
    gmpRisk: 'gmp_critical',
    dataIntegrityRisk: 'high',
    euGmpChapter: 'EU GMP Chapter 5, GACP',
  },
  extraction: {
    gmpRisk: 'gmp_critical',
    dataIntegrityRisk: 'high',
    euGmpChapter: 'EU GMP Chapter 5',
  },
  packaging: {
    gmpRisk: 'gmp_critical',
    dataIntegrityRisk: 'medium',
    euGmpChapter: 'EU GMP Chapter 5, Annex 9',
  },
  warehouse: {
    gmpRisk: 'gmp_relevant',
    dataIntegrityRisk: 'medium',
    euGmpChapter: 'EU GMP Chapter 3, GDP',
  },
  engineering: {
    gmpRisk: 'gmp_relevant',
    dataIntegrityRisk: 'medium',
    euGmpChapter: 'EU GMP Chapter 3, Annex 15',
  },
}

/**
 * Get GMP risk classification from department
 */
export function getGMPRiskFromDepartment(department: string): {
  gmpRisk: 'gmp_critical' | 'gmp_relevant' | 'administrative'
  dataIntegrityRisk: 'high' | 'medium' | 'low'
  euGmpChapter: string
} {
  return DEPARTMENT_GMP_RISK_MAP[department] || {
    gmpRisk: 'gmp_relevant',
    dataIntegrityRisk: 'medium',
    euGmpChapter: 'EU GMP Part I',
  }
}
