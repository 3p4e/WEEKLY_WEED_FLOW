import { useCallback } from 'react'
import { motion } from 'framer-motion'
import { RefreshCw, Home } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useCurrentTheme } from '../context/ThemeContext'
import { useWorkflowStore } from '../stores/useWorkflowStore'
import {
  AgentStepper,
  MetadataFormView,
  QuestionnaireView,
  AutomatedProcessingView,
  QAReviewInterface,
  DocumentGenerationView,
} from '../components/workflow'
import type { AgentNumber } from '../types/workflow'

/**
 * CreateSOPPage - New 9-Agent Interactive Workflow
 * Orchestrates the complete SOP creation process through 9 sequential agents
 */
export default function CreateSOPPage() {
  const theme = useCurrentTheme()
  const navigate = useNavigate()

  const {
    currentAgent,
    currentPhase,
    agents,
    setCurrentAgent,
    reset,
    sopDocument,
    processingStatus,
  } = useWorkflowStore()

  // Check if workflow is complete (document generated)
  const isWorkflowComplete = sopDocument !== null || processingStatus?.phase === 'complete'

  // Handle agent navigation (only completed agents can be revisited)
  const handleAgentClick = useCallback((agent: AgentNumber) => {
    const agentInfo = agents.find(a => a.number === agent)
    if (agentInfo && (agentInfo.status === 'completed' || agent === currentAgent)) {
      setCurrentAgent(agent)
    }
  }, [agents, currentAgent, setCurrentAgent])

  // Handle workflow reset
  const handleReset = () => {
    if (window.confirm('Are you sure you want to start over? All progress will be lost.')) {
      reset()
    }
  }

  // Render the appropriate view based on current phase
  const renderAgentView = () => {
    // If workflow is complete, show document generation view with download
    if (isWorkflowComplete && (currentPhase === 'automated_compliance' || currentPhase === 'automated_raci' || currentPhase === 'formatting')) {
      return <DocumentGenerationView agentNumber={7} />
    }

    switch (currentPhase) {
      case 'metadata':
        return <MetadataFormView />

      case 'questionnaire_intro':
        return <QuestionnaireView agentNumber={2} />

      case 'questionnaire_procedure':
        return <QuestionnaireView agentNumber={3} />

      case 'automated_compliance':
        return <AutomatedProcessingView agentNumber={4} />

      case 'automated_raci':
        return <AutomatedProcessingView agentNumber={5} />

      case 'qa_review':
        return <QAReviewInterface />

      case 'formatting':
        return <DocumentGenerationView agentNumber={7} />

      case 'questionnaire_annex':
        return <QuestionnaireView agentNumber={8} />

      case 'annex_formatting':
        return <DocumentGenerationView agentNumber={9} />

      case 'complete':
        return (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="max-w-2xl mx-auto text-center py-16"
          >
            <div
              className="w-24 h-24 rounded-full flex items-center justify-center mx-auto mb-6 text-5xl"
              style={{
                background: `linear-gradient(135deg, ${theme.colors.success}30, ${theme.colors.primary}30)`,
              }}
            >
              🎉
            </div>
            <h1
              className="text-3xl font-bold mb-4"
              style={{ color: theme.colors.success }}
            >
              SOP Generation Complete!
            </h1>
            <p
              className="text-lg mb-8"
              style={{ color: theme.colors.gray }}
            >
              Your SOP and all annexes have been successfully generated.
              You can download them from Agent 7 or revisit any step above.
            </p>
            <div className="flex justify-center gap-4">
              <button
                onClick={() => navigate('/documents')}
                className="flex items-center gap-2 px-6 py-3 rounded-lg font-semibold"
                style={{
                  background: `linear-gradient(135deg, ${theme.colors.primary}, ${theme.colors.secondary})`,
                  color: '#fff',
                }}
              >
                View Documents
              </button>
              <button
                onClick={handleReset}
                className="flex items-center gap-2 px-6 py-3 rounded-lg"
                style={{
                  backgroundColor: 'transparent',
                  color: theme.colors.gray,
                  border: `1px solid ${theme.colors.border}`,
                }}
              >
                <RefreshCw size={18} />
                Create Another
              </button>
            </div>
          </motion.div>
        )

      default:
        return <MetadataFormView />
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header with Agent Stepper */}
      <div
        className="shrink-0 border-b px-6 py-4"
        style={{
          backgroundColor: `${theme.colors.darkBg}90`,
          borderColor: theme.colors.border,
          backdropFilter: 'blur(10px)',
        }}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/')}
              className="p-2 rounded-lg transition-colors hover:bg-white/10"
              style={{ color: theme.colors.gray }}
              title="Back to Dashboard"
            >
              <Home size={20} />
            </button>
            <div>
              <h1
                className="text-xl font-bold"
                style={{ color: theme.colors.primary }}
              >
                Create New SOP
              </h1>
              <p className="text-sm" style={{ color: theme.colors.gray }}>
                9-Agent Interactive Workflow
              </p>
            </div>
          </div>
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors hover:bg-white/10"
            style={{ color: theme.colors.gray }}
            title="Reset workflow"
          >
            <RefreshCw size={16} />
            Reset
          </button>
        </div>

        <AgentStepper
          agents={agents}
          currentAgent={currentAgent}
          onAgentClick={handleAgentClick}
        />
      </div>

      {/* Main Content Area */}
      <div
        className="flex-1 overflow-hidden"
        style={{ backgroundColor: theme.colors.darkBg }}
      >
        <div className="h-full overflow-y-auto">
          <div className="p-6">
            <motion.div
              key={currentPhase}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
            >
              {renderAgentView()}
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  )
}
