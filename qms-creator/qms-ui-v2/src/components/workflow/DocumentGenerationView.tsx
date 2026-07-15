import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  Download,
  Mail,
  CheckCircle2,
  Loader2,
  FileCheck,
  AlertCircle,
  Eye,
} from 'lucide-react'
import { useCurrentTheme } from '../../context/ThemeContext'
import { useWorkflowStore } from '../../stores/useWorkflowStore'
import { DocumentPreview } from '../document'
import type { AgentNumber, GeneratedDocument } from '../../types/workflow'
import { AGENT_DEFINITIONS } from '../../types/workflow'

interface DocumentGenerationViewProps {
  agentNumber: AgentNumber // 7 or 9
}

interface GenerationStep {
  id: string
  label: string
  status: 'pending' | 'in_progress' | 'completed'
}

/**
 * DocumentGenerationView Component
 * Agent 7: Document Formatter - SOP generation
 * Agent 9: Annex Formatter - Annex generation
 */
export function DocumentGenerationView({ agentNumber }: DocumentGenerationViewProps) {
  const theme = useCurrentTheme()
  const agentInfo = AGENT_DEFINITIONS.find(a => a.number === agentNumber)

  const {
    sopDocument,
    annexDocuments,
    metadata,
    error,
  } = useWorkflowStore()

  // Local state
  const [steps, setSteps] = useState<GenerationStep[]>([])
  const [showPreview, setShowPreview] = useState(false)
  const [currentDocument, setCurrentDocument] = useState<GeneratedDocument | null>(null)

  // Initialize steps based on agent
  useEffect(() => {
    const agent7Steps: GenerationStep[] = [
      { id: 'theme', label: 'Applying document theme', status: 'pending' },
      { id: 'cover', label: 'Generating cover page', status: 'pending' },
      { id: 'toc', label: 'Creating table of contents', status: 'pending' },
      { id: 'sections', label: 'Formatting sections', status: 'pending' },
      { id: 'tables', label: 'Rendering tables', status: 'pending' },
      { id: 'raci', label: 'Inserting RACI matrix', status: 'pending' },
      { id: 'headers', label: 'Adding headers and footers', status: 'pending' },
      { id: 'watermark', label: 'Applying DRAFT watermark', status: 'pending' },
      { id: 'finalize', label: 'Finalizing document', status: 'pending' },
    ]

    const agent9Steps: GenerationStep[] = [
      { id: 'analyze', label: 'Analyzing annex content', status: 'pending' },
      { id: 'format', label: 'Formatting annex structure', status: 'pending' },
      { id: 'tables', label: 'Creating form tables', status: 'pending' },
      { id: 'fields', label: 'Adding input fields', status: 'pending' },
      { id: 'link', label: 'Linking to main SOP', status: 'pending' },
      { id: 'finalize', label: 'Finalizing annex', status: 'pending' },
    ]

    setSteps(agentNumber === 7 ? agent7Steps : agent9Steps)
  }, [agentNumber])

  // Skip simulation if document already exists (backend generated it)
  useEffect(() => {
    if (sopDocument && agentNumber === 7) {
      // Mark all steps as completed since document is ready
      setSteps(prev => prev.map(step => ({ ...step, status: 'completed' })))
      return
    }

    // Only run simulation if no document exists yet
    if (steps.length === 0 || sopDocument) return

    let currentStepIndex = 0
    const interval = setInterval(() => {
      if (currentStepIndex >= steps.length) {
        clearInterval(interval)

        // Set document when complete
        if (agentNumber === 7 && !sopDocument) {
          setCurrentDocument({
            path: '/generated/QA_02.05_Document_Control.docx',
            filename: `${metadata?.documentCode || 'QA_02.05'}_Document_Control.docx`,
            size: 245760,
            generatedAt: new Date(),
            downloadUrl: '/api/documents/download/latest',
            previewUrl: '/api/documents/preview/latest',
          })
        }
        return
      }

      setSteps(prev => prev.map((step, idx) => {
        if (idx < currentStepIndex) {
          return { ...step, status: 'completed' }
        } else if (idx === currentStepIndex) {
          return { ...step, status: 'in_progress' }
        }
        return step
      }))

      currentStepIndex++
    }, 1500)

    return () => clearInterval(interval)
  }, [steps.length, agentNumber, sopDocument, metadata])

  const completedSteps = steps.filter(s => s.status === 'completed').length
  const progress = steps.length > 0 ? (completedSteps / steps.length) * 100 : 0
  const isComplete = completedSteps === steps.length && steps.length > 0
  const document = agentNumber === 7 ? (sopDocument || currentDocument) : annexDocuments[0]

  const handleDownload = () => {
    if (document?.downloadUrl) {
      window.open(document.downloadUrl, '_blank')
    }
  }

  const handleEmail = () => {
    if (document) {
      const subject = encodeURIComponent(`Generated SOP: ${document.filename}`)
      const body = encodeURIComponent(`Please find attached the generated SOP document: ${document.filename}`)
      window.location.href = `mailto:?subject=${subject}&body=${body}`
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

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
            <p className="font-semibold" style={{ color: theme.colors.error }}>Generation Error</p>
            <p className="text-sm" style={{ color: theme.colors.error }}>{error}</p>
          </div>
        </motion.div>
      )}

      {/* Main Card */}
      <div
        className="rounded-xl overflow-hidden"
        style={{
          backgroundColor: theme.colors.lightBg,
          border: `1px solid ${theme.colors.border}`,
        }}
      >
        {/* Progress Section */}
        <div
          className="p-6"
          style={{
            background: isComplete
              ? `linear-gradient(135deg, ${theme.colors.success}15, ${theme.colors.primary}15)`
              : `linear-gradient(135deg, ${theme.colors.primary}15, ${theme.colors.secondary}15)`,
          }}
        >
          {/* Status Header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              {isComplete ? (
                <CheckCircle2 size={28} style={{ color: theme.colors.success }} />
              ) : (
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                >
                  <Loader2 size={28} style={{ color: theme.colors.primary }} />
                </motion.div>
              )}
              <div>
                <span
                  className="font-semibold text-lg"
                  style={{ color: isComplete ? theme.colors.success : theme.colors.primary }}
                >
                  {isComplete ? 'Document Generated!' : 'Generating Document...'}
                </span>
                {document && (
                  <p className="text-sm" style={{ color: theme.colors.gray }}>
                    {document.filename}
                  </p>
                )}
              </div>
            </div>
            <span
              className="text-3xl font-bold"
              style={{ color: isComplete ? theme.colors.success : theme.colors.primary }}
            >
              {Math.round(progress)}%
            </span>
          </div>

          {/* Progress Bar */}
          <div
            className="h-4 rounded-full overflow-hidden"
            style={{ backgroundColor: theme.colors.border }}
          >
            <motion.div
              className="h-full"
              style={{
                background: isComplete
                  ? theme.colors.success
                  : `linear-gradient(90deg, ${theme.colors.primary}, ${theme.colors.secondary})`,
              }}
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>

        {/* Steps List */}
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {steps.map((step, index) => (
              <motion.div
                key={step.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                className="flex items-center gap-3 p-3 rounded-lg"
                style={{
                  backgroundColor: step.status === 'in_progress'
                    ? `${theme.colors.primary}15`
                    : 'transparent',
                }}
              >
                {/* Status Icon */}
                <div className="w-6 h-6 flex items-center justify-center shrink-0">
                  {step.status === 'completed' ? (
                    <CheckCircle2 size={18} style={{ color: theme.colors.success }} />
                  ) : step.status === 'in_progress' ? (
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    >
                      <Loader2 size={18} style={{ color: theme.colors.primary }} />
                    </motion.div>
                  ) : (
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: theme.colors.border }}
                    />
                  )}
                </div>

                {/* Step Label */}
                <span
                  className="text-sm"
                  style={{
                    color: step.status === 'completed'
                      ? theme.colors.success
                      : step.status === 'in_progress'
                      ? theme.colors.primary
                      : theme.colors.gray,
                  }}
                >
                  {step.label}
                </span>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Document Info & Actions */}
        {isComplete && document && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-6 border-t"
            style={{ borderColor: theme.colors.border }}
          >
            {/* Document Card */}
            <div
              className="p-4 rounded-lg flex items-center gap-4 mb-6"
              style={{
                backgroundColor: `${theme.colors.success}10`,
                border: `1px solid ${theme.colors.success}30`,
              }}
            >
              <div
                className="w-14 h-14 rounded-lg flex items-center justify-center"
                style={{ backgroundColor: `${theme.colors.success}20` }}
              >
                <FileCheck size={28} style={{ color: theme.colors.success }} />
              </div>
              <div className="flex-1">
                <p className="font-semibold" style={{ color: '#fff' }}>
                  {document.filename}
                </p>
                <div className="flex items-center gap-4 text-sm" style={{ color: theme.colors.gray }}>
                  <span>{formatFileSize(document.size)}</span>
                  <span>•</span>
                  <span>{document.generatedAt.toLocaleString()}</span>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap gap-3">
              <button
                onClick={handleDownload}
                className="flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all"
                style={{
                  background: `linear-gradient(135deg, ${theme.colors.primary}, ${theme.colors.secondary})`,
                  color: '#fff',
                  boxShadow: `0 4px 15px ${theme.colors.primary}40`,
                }}
              >
                <Download size={18} />
                Download DOCX
              </button>

              <button
                onClick={() => setShowPreview(true)}
                className="flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all"
                style={{
                  backgroundColor: `${theme.colors.secondary}20`,
                  color: theme.colors.secondary,
                  border: `1px solid ${theme.colors.secondary}40`,
                }}
              >
                <Eye size={18} />
                Preview
              </button>

              <button
                onClick={handleEmail}
                className="flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all"
                style={{
                  backgroundColor: 'transparent',
                  color: theme.colors.gray,
                  border: `1px solid ${theme.colors.border}`,
                }}
              >
                <Mail size={18} />
                Send via Email
              </button>
            </div>
          </motion.div>
        )}
      </div>

      {/* Document Preview Modal */}
      {showPreview && document && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.8)' }}
          onClick={() => setShowPreview(false)}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="w-full max-w-5xl h-[80vh]"
            onClick={(e) => e.stopPropagation()}
          >
            <DocumentPreview
              documentUrl={document.previewUrl}
              title={document.filename}
              height="100%"
              showDownload={true}
              downloadFilename={document.filename}
            />
          </motion.div>
        </motion.div>
      )}

      {/* Continue Info */}
      {isComplete && agentNumber === 7 && metadata?.annexes && metadata.annexes.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-6 p-4 rounded-lg text-center"
          style={{
            backgroundColor: `${theme.colors.info}10`,
            border: `1px solid ${theme.colors.info}30`,
          }}
        >
          <p className="text-sm" style={{ color: theme.colors.info }}>
            Main SOP document generated. Proceeding to Agent 8 for annex generation...
          </p>
          <p className="text-xs mt-1" style={{ color: theme.colors.gray }}>
            {metadata.annexes.length} annex{metadata.annexes.length > 1 ? 'es' : ''} to generate
          </p>
        </motion.div>
      )}

      {!isComplete && (
        <div
          className="mt-6 p-4 rounded-lg text-center"
          style={{
            backgroundColor: `${theme.colors.info}10`,
            border: `1px solid ${theme.colors.info}30`,
          }}
        >
          <p className="text-sm" style={{ color: theme.colors.info }}>
            <Loader2 size={14} className="inline mr-2 animate-spin" />
            Generating your document. This may take a moment...
          </p>
        </div>
      )}
    </div>
  )
}

export default DocumentGenerationView
