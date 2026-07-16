import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import {
  Loader2,
  CheckCircle2,
  Database,
  FileText,
  Users,
  Sparkles,
  AlertCircle,
  RefreshCw,
} from 'lucide-react'
import { useCurrentTheme } from '../../context/ThemeContext'
import { useWorkflowStore } from '../../stores/useWorkflowStore'
import type { AgentNumber } from '../../types/workflow'
import { AGENT_DEFINITIONS } from '../../types/workflow'

interface AutomatedProcessingViewProps {
  agentNumber: AgentNumber // 4 or 5
}

interface ProcessingStep {
  id: string
  label: string
  status: 'pending' | 'in_progress' | 'completed' | 'error'
  message?: string
  timestamp?: Date
}

/**
 * AutomatedProcessingView Component
 * Display for Agents 4 (Compliance Integrator) and 5 (RACI Specialist)
 * Shows real-time processing status, streaming content preview
 */
export function AutomatedProcessingView({ agentNumber }: AutomatedProcessingViewProps) {
  const theme = useCurrentTheme()
  const agentInfo = AGENT_DEFINITIONS.find(a => a.number === agentNumber)

  const {
    processingStatus,
    setProcessingStatus,
    error,
  } = useWorkflowStore()

  // Local state for streaming content
  const [streamingContent, setStreamingContent] = useState<string>('')
  const [steps, setSteps] = useState<ProcessingStep[]>([])
  const contentRef = useRef<HTMLDivElement>(null)

  // Initialize steps based on agent
  useEffect(() => {
    const agent4Steps: ProcessingStep[] = [
      { id: 'analyze', label: 'Analyzing procedure content', status: 'pending' },
      { id: 'extract_terms', label: 'Extracting technical terms', status: 'pending' },
      { id: 'query_db1', label: 'Querying regulatory database (DB1)', status: 'pending' },
      { id: 'query_db2', label: 'Querying operational database (DB2)', status: 'pending' },
      { id: 'generate_definitions', label: 'Generating definitions section', status: 'pending' },
      { id: 'compile_references', label: 'Compiling document references', status: 'pending' },
      { id: 'create_training', label: 'Creating training requirements', status: 'pending' },
    ]

    const agent5Steps: ProcessingStep[] = [
      { id: 'analyze_roles', label: 'Analyzing roles from procedure', status: 'pending' },
      { id: 'identify_activities', label: 'Identifying key activities', status: 'pending' },
      { id: 'map_responsibilities', label: 'Mapping responsibilities', status: 'pending' },
      { id: 'generate_matrix', label: 'Generating RACI matrix', status: 'pending' },
      { id: 'validate', label: 'Validating assignments', status: 'pending' },
    ]

    setSteps(agentNumber === 4 ? agent4Steps : agent5Steps)
  }, [agentNumber])

  // Simulate processing (in real implementation, this connects to SSE)
  useEffect(() => {
    if (steps.length === 0) return

    let currentStepIndex = 0
    const interval = setInterval(() => {
      if (currentStepIndex >= steps.length) {
        clearInterval(interval)
        return
      }

      setSteps(prev => prev.map((step, idx) => {
        if (idx < currentStepIndex) {
          return { ...step, status: 'completed', timestamp: new Date() }
        } else if (idx === currentStepIndex) {
          return { ...step, status: 'in_progress' }
        }
        return step
      }))

      // Update processing status
      const progress = Math.round(((currentStepIndex + 1) / steps.length) * 100)
      setProcessingStatus({
        agent: agentNumber,
        phase: steps[currentStepIndex].id,
        message: steps[currentStepIndex].label,
        progress,
      })

      // Simulate content streaming
      if (agentNumber === 4 && currentStepIndex >= 4) {
        const sampleContent = getSampleContentForStep(currentStepIndex)
        setStreamingContent(prev => prev + sampleContent)
      }

      currentStepIndex++
    }, 2000) // 2 seconds per step for demo

    return () => clearInterval(interval)
  }, [steps.length, agentNumber, setProcessingStatus])

  // Auto-scroll content preview
  useEffect(() => {
    if (contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [streamingContent])

  const progress = processingStatus?.agent === agentNumber ? processingStatus.progress : 0
  const isComplete = progress === 100

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-4">
          <motion.div
            className="w-16 h-16 rounded-xl flex items-center justify-center text-3xl"
            style={{ backgroundColor: `${theme.colors.primary}20` }}
            animate={!isComplete ? { scale: [1, 1.05, 1] } : undefined}
            transition={{ duration: 2, repeat: Infinity }}
          >
            {agentInfo?.icon}
          </motion.div>
          <div>
            <h1 className="text-2xl font-bold" style={{ color: theme.colors.primary }}>
              Agent {agentNumber}: {agentInfo?.name}
            </h1>
            <p style={{ color: theme.colors.gray }}>
              {agentInfo?.description}
            </p>
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 p-4 rounded-lg flex items-start gap-3"
          style={{
            backgroundColor: `${theme.colors.error}20`,
            borderLeft: `3px solid ${theme.colors.error}`,
          }}
        >
          <AlertCircle size={20} style={{ color: theme.colors.error }} />
          <div>
            <p className="font-semibold" style={{ color: theme.colors.error }}>Processing Error</p>
            <p className="text-sm" style={{ color: theme.colors.error }}>{error}</p>
          </div>
        </motion.div>
      )}

      {/* Main Processing Card */}
      <div
        className="rounded-xl overflow-hidden"
        style={{
          backgroundColor: theme.colors.lightBg,
          border: `1px solid ${theme.colors.border}`,
        }}
      >
        {/* Progress Header */}
        <div
          className="p-6"
          style={{
            background: `linear-gradient(135deg, ${theme.colors.primary}15, ${theme.colors.secondary}15)`,
          }}
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              {isComplete ? (
                <CheckCircle2 size={24} style={{ color: theme.colors.success }} />
              ) : (
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                >
                  <Loader2 size={24} style={{ color: theme.colors.primary }} />
                </motion.div>
              )}
              <span
                className="font-semibold"
                style={{ color: isComplete ? theme.colors.success : theme.colors.primary }}
              >
                {isComplete ? 'Processing Complete' : 'Processing...'}
              </span>
            </div>
            <span
              className="text-2xl font-bold"
              style={{ color: theme.colors.primary }}
            >
              {progress}%
            </span>
          </div>

          {/* Progress Bar */}
          <div
            className="h-3 rounded-full overflow-hidden"
            style={{ backgroundColor: theme.colors.border }}
          >
            <motion.div
              className="h-full"
              style={{
                background: `linear-gradient(90deg, ${theme.colors.primary}, ${theme.colors.secondary})`,
              }}
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>

        {/* Processing Steps */}
        <div className="p-6">
          <h3
            className="text-sm font-semibold mb-4 flex items-center gap-2"
            style={{ color: theme.colors.gray }}
          >
            <RefreshCw size={14} />
            Processing Steps
          </h3>

          <div className="space-y-3">
            {steps.map((step, index) => (
              <motion.div
                key={step.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="flex items-center gap-3"
              >
                {/* Status Icon */}
                <div className="w-8 h-8 flex items-center justify-center shrink-0">
                  {step.status === 'completed' ? (
                    <CheckCircle2 size={20} style={{ color: theme.colors.success }} />
                  ) : step.status === 'in_progress' ? (
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    >
                      <Loader2 size={20} style={{ color: theme.colors.primary }} />
                    </motion.div>
                  ) : step.status === 'error' ? (
                    <AlertCircle size={20} style={{ color: theme.colors.error }} />
                  ) : (
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: theme.colors.border }}
                    />
                  )}
                </div>

                {/* Step Content */}
                <div className="flex-1">
                  <p
                    className={`text-sm ${step.status === 'in_progress' ? 'font-medium' : ''}`}
                    style={{
                      color: step.status === 'completed'
                        ? theme.colors.success
                        : step.status === 'in_progress'
                        ? theme.colors.primary
                        : theme.colors.gray,
                    }}
                  >
                    {step.label}
                  </p>
                  {step.message && (
                    <p className="text-xs" style={{ color: theme.colors.gray }}>
                      {step.message}
                    </p>
                  )}
                </div>

                {/* Step indicator icon */}
                <div className="shrink-0">
                  {step.id.includes('db1') && (
                    <Database size={14} style={{ color: theme.colors.info }} />
                  )}
                  {step.id.includes('db2') && (
                    <Database size={14} style={{ color: theme.colors.accent }} />
                  )}
                  {step.id.includes('raci') || step.id.includes('roles') ? (
                    <Users size={14} style={{ color: theme.colors.secondary }} />
                  ) : null}
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Content Preview */}
        {(streamingContent || agentNumber === 5) && (
          <div
            className="border-t"
            style={{ borderColor: theme.colors.border }}
          >
            <div className="p-4 flex items-center gap-2">
              <FileText size={16} style={{ color: theme.colors.secondary }} />
              <h3
                className="text-sm font-semibold"
                style={{ color: theme.colors.secondary }}
              >
                {agentNumber === 4 ? 'Generated Content Preview' : 'RACI Matrix Preview'}
              </h3>
              <Sparkles size={14} style={{ color: theme.colors.accent }} />
            </div>

            <div
              ref={contentRef}
              className="max-h-64 overflow-y-auto p-4 font-mono text-sm"
              style={{
                backgroundColor: `${theme.colors.darkBg}80`,
                color: theme.colors.gray,
              }}
            >
              {agentNumber === 4 ? (
                <pre className="whitespace-pre-wrap">{streamingContent || 'Waiting for content...'}</pre>
              ) : (
                <RACIPreview />
              )}
            </div>
          </div>
        )}
      </div>

      {/* Bottom Info */}
      <div
        className="mt-6 p-4 rounded-lg text-center"
        style={{
          backgroundColor: `${theme.colors.info}10`,
          border: `1px solid ${theme.colors.info}30`,
        }}
      >
        <p className="text-sm" style={{ color: theme.colors.info }}>
          {isComplete ? (
            <>
              <CheckCircle2 size={14} className="inline mr-1" />
              Agent {agentNumber} has completed. Moving to Agent {agentNumber + 1}...
            </>
          ) : (
            <>
              <Loader2 size={14} className="inline mr-1 animate-spin" />
              This is an automated process. Please wait while the agent completes its tasks.
            </>
          )}
        </p>
      </div>
    </div>
  )
}

// Sample content generator for demo
function getSampleContentForStep(stepIndex: number): string {
  const contents = [
    '',
    '',
    '',
    '',
    `
## 1.5 Abbreviations and Definitions

| Term | Definition |
|------|------------|
| GACP | Good Agricultural and Collection Practices |
| EU GMP | European Union Good Manufacturing Practice |
`,
    `| SOP | Standard Operating Procedure |
| QA | Quality Assurance |
| QC | Quality Control |
`,
    `
## 5.0 Associated Documents and Cross-References

| Document Code | Document Title | Relevance |
|--------------|----------------|-----------|
| QA_01.01 | Quality Manual | Master reference |
| QC_02.03 | Sampling Procedures | Related procedure |
`,
  ]
  return contents[stepIndex] || ''
}

// RACI Matrix Preview Component
function RACIPreview() {
  const theme = useCurrentTheme()
  const { raciMatrix } = useWorkflowStore()

  // Sample RACI for demo
  const sampleRaci = raciMatrix || {
    roles: ['QA Manager', 'Production', 'QC', 'Warehouse'],
    activities: [
      { activity: 'Document Review', assignments: { 'QA Manager': 'R', 'Production': 'C', 'QC': 'I', 'Warehouse': 'I' } },
      { activity: 'Batch Release', assignments: { 'QA Manager': 'A', 'Production': 'R', 'QC': 'C', 'Warehouse': 'I' } },
      { activity: 'Record Retention', assignments: { 'QA Manager': 'A', 'Production': 'I', 'QC': 'I', 'Warehouse': 'R' } },
    ],
  }

  const getRaciColor = (value: string) => {
    switch (value) {
      case 'R': return theme.colors.primary
      case 'A': return theme.colors.error
      case 'C': return theme.colors.warning
      case 'I': return theme.colors.info
      default: return theme.colors.gray
    }
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr>
            <th className="text-left p-2" style={{ color: theme.colors.gray }}>Activity</th>
            {sampleRaci.roles.map(role => (
              <th key={role} className="text-center p-2" style={{ color: theme.colors.gray }}>
                {role}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sampleRaci.activities.map((activity, idx) => (
            <tr key={idx} style={{ borderTop: `1px solid ${theme.colors.border}` }}>
              <td className="p-2" style={{ color: '#fff' }}>{activity.activity}</td>
              {sampleRaci.roles.map(role => {
                const value = activity.assignments[role] as 'R' | 'A' | 'C' | 'I' | undefined
                return (
                  <td key={role} className="text-center p-2">
                    {value && (
                      <span
                        className="inline-block w-6 h-6 rounded font-bold"
                        style={{
                          backgroundColor: `${getRaciColor(value)}30`,
                          color: getRaciColor(value),
                          lineHeight: '24px',
                        }}
                      >
                        {value}
                      </span>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-4 flex gap-4 text-xs">
        <span style={{ color: theme.colors.primary }}>R = Responsible</span>
        <span style={{ color: theme.colors.error }}>A = Accountable</span>
        <span style={{ color: theme.colors.warning }}>C = Consulted</span>
        <span style={{ color: theme.colors.info }}>I = Informed</span>
      </div>
    </div>
  )
}

export default AutomatedProcessingView
