import { create } from 'zustand'
import type {
  WorkflowState,
  AgentNumber,
  AgentInfo,
  MetadataFormData,
  QuestionnaireResponse,
  QASelection,
  Question,
  GeneratedContent,
  RACIMatrix,
  QAReviewReport,
  GeneratedDocument,
  ProcessingStatus,
  DocumentGenerationStatus,
} from '../types/workflow'
import { AGENT_DEFINITIONS } from '../types/workflow'

interface WorkflowActions {
  // Navigation
  setCurrentAgent: (agent: AgentNumber) => void
  goToNextAgent: () => void
  goToPreviousAgent: () => void
  setAgentStatus: (agent: AgentNumber, status: 'pending' | 'in_progress' | 'completed' | 'skipped') => void

  // Agent 1: Metadata
  setMetadata: (data: MetadataFormData) => void
  submitMetadata: () => Promise<void>

  // Agent 2: Introduction
  setIntroQuestions: (questions: Question[]) => void
  answerIntroQuestion: (questionId: string, answer: string | string[]) => void
  submitIntroAnswers: () => Promise<void>

  // Agent 3: Procedure
  setProcedureQuestions: (questions: Question[]) => void
  answerProcedureQuestion: (questionId: string, answer: string | string[]) => void
  submitProcedureAnswers: () => Promise<void>

  // Agent 4/5: Automated Processing
  setProcessingStatus: (status: ProcessingStatus) => void
  setComplianceContent: (content: GeneratedContent) => void
  setRACIMatrix: (matrix: RACIMatrix) => void

  // Agent 6: QA Review
  setQAReview: (review: QAReviewReport) => void
  setQASelection: (selection: QASelection) => void
  submitQAApproval: () => Promise<void>

  // Agent 7: Document Formatting
  setFormattingStatus: (status: DocumentGenerationStatus) => void
  setSOPDocument: (doc: GeneratedDocument) => void

  // Agent 8/9: Annexes
  setAnnexQuestions: (annexId: string, questions: Question[]) => void
  answerAnnexQuestion: (annexId: string, questionId: string, answer: string | string[]) => void
  submitAnnexAnswers: (annexId: string) => Promise<void>
  addAnnexDocument: (doc: GeneratedDocument) => void

  // Error handling
  setError: (error: string | null) => void
  clearError: () => void

  // Reset
  reset: () => void
}

const initialAgents: AgentInfo[] = AGENT_DEFINITIONS.map(def => ({
  ...def,
  status: 'pending' as const,
}))

const initialState: WorkflowState = {
  currentAgent: 1,
  currentPhase: 'metadata',
  agents: initialAgents,

  metadata: null,
  workflowId: null,

  introQuestions: [],
  introAnswers: [],

  procedureQuestions: [],
  procedureAnswers: [],

  complianceContent: null,
  raciMatrix: null,
  processingStatus: null,

  qaReview: null,
  qaSelections: [],

  sopDocument: null,
  formattingStatus: null,

  annexQuestionnaires: {},
  annexDocuments: [],

  isProcessing: false,
  error: null,
  canProceed: false,
}

export const useWorkflowStore = create<WorkflowState & WorkflowActions>((set, get) => ({
  ...initialState,

  // ═══════════════════════════════════════════════════════════════
  // NAVIGATION
  // ═══════════════════════════════════════════════════════════════

  setCurrentAgent: (agent: AgentNumber) => {
    const agentInfo = AGENT_DEFINITIONS.find(a => a.number === agent)
    if (!agentInfo) return

    set({
      currentAgent: agent,
      currentPhase: agentInfo.phase,
    })
  },

  goToNextAgent: () => {
    const { currentAgent } = get()
    if (currentAgent < 9) {
      get().setCurrentAgent((currentAgent + 1) as AgentNumber)
    }
  },

  goToPreviousAgent: () => {
    const { currentAgent } = get()
    if (currentAgent > 1) {
      get().setCurrentAgent((currentAgent - 1) as AgentNumber)
    }
  },

  setAgentStatus: (agent: AgentNumber, status) => {
    set(state => ({
      agents: state.agents.map(a =>
        a.number === agent ? { ...a, status } : a
      ),
    }))
  },

  // ═══════════════════════════════════════════════════════════════
  // AGENT 1: METADATA
  // ═══════════════════════════════════════════════════════════════

  setMetadata: (data: MetadataFormData) => {
    set({ metadata: data, canProceed: true })
  },

  submitMetadata: async () => {
    const { metadata } = get()
    if (!metadata) return

    set({ isProcessing: true, error: null })
    get().setAgentStatus(1, 'in_progress')

    try {
      // Convert camelCase to snake_case for backend API
      const metadataPayload = {
        sop_title: metadata.sopTitle,
        short_description: metadata.shortDescription,
        department: metadata.department,
        document_code: metadata.documentCode,
        annexes: metadata.annexes,
      }

      const response = await fetch('/api/workflow/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ metadata: metadataPayload }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to submit metadata')
      }

      const data = await response.json()

      // Set workflow ID and Agent 2 questions from response
      set({
        workflowId: data.workflow_id,
        introQuestions: data.questions || [],
      })

      get().setAgentStatus(1, 'completed')
      get().setAgentStatus(2, 'in_progress')
      get().goToNextAgent()
    } catch (error) {
      set({ error: (error as Error).message })
      get().setAgentStatus(1, 'pending')
    } finally {
      set({ isProcessing: false })
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // AGENT 2: INTRODUCTION
  // ═══════════════════════════════════════════════════════════════

  setIntroQuestions: (questions: Question[]) => {
    set({ introQuestions: questions })
  },

  answerIntroQuestion: (questionId: string, answer: string | string[]) => {
    set(state => {
      const existing = state.introAnswers.findIndex(a => a.questionId === questionId)
      const newAnswer: QuestionnaireResponse = {
        questionId,
        answer,
        timestamp: new Date(),
      }

      const newAnswers = [...state.introAnswers]
      if (existing >= 0) {
        newAnswers[existing] = newAnswer
      } else {
        newAnswers.push(newAnswer)
      }

      // Check if all questions answered
      const allAnswered = state.introQuestions.every(q =>
        newAnswers.some(a => a.questionId === q.id)
      )

      return {
        introAnswers: newAnswers,
        canProceed: allAnswered,
      }
    })
  },

  submitIntroAnswers: async () => {
    const { introAnswers, workflowId } = get()

    set({ isProcessing: true, error: null })

    try {
      if (!workflowId) {
        throw new Error('Workflow not initialized. Please submit metadata first.')
      }

      // Convert answers to the format expected by backend
      const answers: Record<string, string | string[]> = {}
      introAnswers.forEach(a => {
        answers[a.questionId] = a.answer
      })

      const response = await fetch('/api/workflow/agent-2/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_id: workflowId,
          answers,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to submit introduction answers')
      }

      const data = await response.json()

      set({
        procedureQuestions: data.questions || [],
      })

      get().setAgentStatus(2, 'completed')
      get().setAgentStatus(3, 'in_progress')
      get().goToNextAgent()
    } catch (error) {
      set({ error: (error as Error).message })
    } finally {
      set({ isProcessing: false })
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // AGENT 3: PROCEDURE
  // ═══════════════════════════════════════════════════════════════

  setProcedureQuestions: (questions: Question[]) => {
    set({ procedureQuestions: questions })
  },

  answerProcedureQuestion: (questionId: string, answer: string | string[]) => {
    set(state => {
      const existing = state.procedureAnswers.findIndex(a => a.questionId === questionId)
      const newAnswer: QuestionnaireResponse = {
        questionId,
        answer,
        timestamp: new Date(),
      }

      const newAnswers = [...state.procedureAnswers]
      if (existing >= 0) {
        newAnswers[existing] = newAnswer
      } else {
        newAnswers.push(newAnswer)
      }

      const allAnswered = state.procedureQuestions.every(q =>
        newAnswers.some(a => a.questionId === q.id)
      )

      return {
        procedureAnswers: newAnswers,
        canProceed: allAnswered,
      }
    })
  },

  submitProcedureAnswers: async () => {
    const { procedureAnswers, workflowId } = get()

    set({ isProcessing: true, error: null })

    try {
      if (!workflowId) {
        throw new Error('Workflow not initialized. Please submit metadata first.')
      }

      // Convert answers to the format expected by backend
      const answers: Record<string, string | string[]> = {}
      procedureAnswers.forEach(a => {
        answers[a.questionId] = a.answer
      })

      const response = await fetch('/api/workflow/agent-3/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_id: workflowId,
          answers,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to submit procedure answers')
      }

      // Agent 3 submission triggers Agents 4-7 (automated)
      get().setAgentStatus(3, 'completed')
      get().setAgentStatus(4, 'in_progress')
      get().goToNextAgent()

      // Start polling for workflow status
      const pollStatus = async () => {
        try {
          const statusResponse = await fetch(`/api/workflow/${workflowId}/status`)
          if (!statusResponse.ok) return

          const status = await statusResponse.json()

          // Update processing status for UI
          if (status.progress) {
            get().setProcessingStatus({
              agent: status.current_agent,
              phase: status.status,
              message: status.progress.message || 'Processing...',
              progress: status.progress.percent || 0,
              contentPreview: status.progress.content_preview,
            })
          }

          // Update agent statuses based on current agent
          const currentAgent = status.current_agent
          if (currentAgent > 4) {
            get().setAgentStatus(4, 'completed')
          }
          if (currentAgent > 5) {
            get().setAgentStatus(5, 'completed')
          }
          if (currentAgent > 6) {
            get().setAgentStatus(6, 'completed')
          }

          // Check if complete or error
          if (status.status === 'complete') {
            // Mark all automated agents as completed
            get().setAgentStatus(4, 'completed')
            get().setAgentStatus(5, 'completed')
            get().setAgentStatus(6, 'completed')
            get().setAgentStatus(7, 'completed')

            // Update processing status to show completion
            get().setProcessingStatus({
              agent: 7,
              phase: 'complete',
              message: 'SOP generation complete!',
              progress: 100,
            })

            if (status.docx_path) {
              get().setSOPDocument({
                path: status.docx_path,
                filename: status.docx_path.split('/').pop() || 'document.docx',
                size: 0,
                generatedAt: new Date(),
                downloadUrl: `/api/download/${encodeURIComponent(status.docx_path)}`,
              })
            }

            // Navigate to Agent 7 (Document) view and mark workflow complete
            get().setCurrentAgent(7)
            set({
              isProcessing: false,
              canProceed: true,
              currentPhase: 'formatting',
            })
            return // Stop polling
          }

          if (status.status === 'error') {
            set({ error: status.error || 'Workflow processing failed', isProcessing: false })
            return // Stop polling
          }

          // Continue polling every 2 seconds
          setTimeout(pollStatus, 2000)
        } catch (pollError) {
          console.error('Status polling error:', pollError)
          setTimeout(pollStatus, 3000) // Retry with longer delay
        }
      }

      // Start polling
      pollStatus()

    } catch (error) {
      set({ error: (error as Error).message, isProcessing: false })
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // AGENT 4/5: AUTOMATED PROCESSING
  // ═══════════════════════════════════════════════════════════════

  setProcessingStatus: (status: ProcessingStatus) => {
    set({ processingStatus: status })

    // If agent 4 completes, move to agent 5
    if (status.agent === 4 && status.progress === 100) {
      get().setAgentStatus(4, 'completed')
      get().setAgentStatus(5, 'in_progress')
    }

    // If agent 5 completes, move to agent 6
    if (status.agent === 5 && status.progress === 100) {
      get().setAgentStatus(5, 'completed')
      get().setAgentStatus(6, 'in_progress')
      get().goToNextAgent()
    }
  },

  setComplianceContent: (content: GeneratedContent) => {
    set({ complianceContent: content })
  },

  setRACIMatrix: (matrix: RACIMatrix) => {
    set({ raciMatrix: matrix })
  },

  // ═══════════════════════════════════════════════════════════════
  // AGENT 6: QA REVIEW
  // ═══════════════════════════════════════════════════════════════

  setQAReview: (review: QAReviewReport) => {
    set({ qaReview: review, canProceed: true })
  },

  setQASelection: (selection: QASelection) => {
    set(state => {
      const existing = state.qaSelections.findIndex(
        s => s.recommendationId === selection.recommendationId
      )
      const newSelections = [...state.qaSelections]
      if (existing >= 0) {
        newSelections[existing] = selection
      } else {
        newSelections.push(selection)
      }
      return { qaSelections: newSelections }
    })
  },

  submitQAApproval: async () => {
    const { qaSelections } = get()

    set({ isProcessing: true, error: null })

    try {
      const response = await fetch('/api/workflow/agent-6/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selections: qaSelections }),
      })

      if (!response.ok) throw new Error('Failed to submit QA approval')

      get().setAgentStatus(6, 'completed')
      get().setAgentStatus(7, 'in_progress')
      get().goToNextAgent()

      // Start listening to SSE for Agent 7 progress
      // TODO: Implement SSE listener
    } catch (error) {
      set({ error: (error as Error).message })
    } finally {
      set({ isProcessing: false })
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // AGENT 7: DOCUMENT FORMATTING
  // ═══════════════════════════════════════════════════════════════

  setFormattingStatus: (status: DocumentGenerationStatus) => {
    set({ formattingStatus: status })

    if (status.progress === 100) {
      get().setAgentStatus(7, 'completed')

      // Check if we need to generate annexes
      const { metadata } = get()
      if (metadata && metadata.annexes.length > 0) {
        get().setAgentStatus(8, 'in_progress')
        get().goToNextAgent()
      } else {
        // No annexes, workflow complete
        get().setCurrentAgent(7) // Stay on Agent 7 to show download
      }
    }
  },

  setSOPDocument: (doc: GeneratedDocument) => {
    set({ sopDocument: doc })
  },

  // ═══════════════════════════════════════════════════════════════
  // AGENT 8/9: ANNEXES
  // ═══════════════════════════════════════════════════════════════

  setAnnexQuestions: (annexId: string, questions: Question[]) => {
    set(state => ({
      annexQuestionnaires: {
        ...state.annexQuestionnaires,
        [annexId]: {
          questions,
          answers: state.annexQuestionnaires[annexId]?.answers || [],
        },
      },
    }))
  },

  answerAnnexQuestion: (annexId: string, questionId: string, answer: string | string[]) => {
    set(state => {
      const questionnaire = state.annexQuestionnaires[annexId]
      if (!questionnaire) return state

      const existing = questionnaire.answers.findIndex(a => a.questionId === questionId)
      const newAnswer: QuestionnaireResponse = {
        questionId,
        answer,
        timestamp: new Date(),
      }

      const newAnswers = [...questionnaire.answers]
      if (existing >= 0) {
        newAnswers[existing] = newAnswer
      } else {
        newAnswers.push(newAnswer)
      }

      return {
        annexQuestionnaires: {
          ...state.annexQuestionnaires,
          [annexId]: {
            ...questionnaire,
            answers: newAnswers,
          },
        },
      }
    })
  },

  submitAnnexAnswers: async (annexId: string) => {
    const { annexQuestionnaires } = get()
    const questionnaire = annexQuestionnaires[annexId]
    if (!questionnaire) return

    set({ isProcessing: true, error: null })

    try {
      const response = await fetch(`/api/workflow/agent-8/annex/${annexId}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers: questionnaire.answers }),
      })

      if (!response.ok) throw new Error('Failed to submit annex answers')

      const data = await response.json()

      // Add the generated annex document
      if (data.document) {
        get().addAnnexDocument(data.document)
      }

      // Check if all annexes are complete
      const { metadata, annexDocuments } = get()
      if (metadata && annexDocuments.length === metadata.annexes.length) {
        // All annexes complete
        get().setAgentStatus(8, 'completed')
        get().setAgentStatus(9, 'completed')
        get().setCurrentAgent(7) // Go back to show all downloads
      }
    } catch (error) {
      set({ error: (error as Error).message })
    } finally {
      set({ isProcessing: false })
    }
  },

  addAnnexDocument: (doc: GeneratedDocument) => {
    set(state => ({
      annexDocuments: [...state.annexDocuments, doc],
    }))
  },

  // ═══════════════════════════════════════════════════════════════
  // ERROR HANDLING
  // ═══════════════════════════════════════════════════════════════

  setError: (error: string | null) => {
    set({ error })
  },

  clearError: () => {
    set({ error: null })
  },

  // ═══════════════════════════════════════════════════════════════
  // RESET
  // ═══════════════════════════════════════════════════════════════

  reset: () => {
    set(initialState)
  },
}))
