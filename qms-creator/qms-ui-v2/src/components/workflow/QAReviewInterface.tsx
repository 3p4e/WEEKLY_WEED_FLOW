import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Info,
  ChevronDown,
  ChevronRight,
  Star,
  Sparkles,
  FileCheck,
  Loader2,
  Check,
} from 'lucide-react'
import { useCurrentTheme } from '../../context/ThemeContext'
import { useWorkflowStore } from '../../stores/useWorkflowStore'
import { DocumentPreview, AnnotationToolbar, CommentThread } from '../document'
import type { TextSelection } from '../document'
import type { Comment } from '../document/CommentThread'
import { AGENT_DEFINITIONS } from '../../types/workflow'

/**
 * QAReviewInterface Component
 * Agent 6: Quality Assembler - Split-panel QA review interface
 * Left: Document preview with annotation support
 * Right: Quality scores and recommendations
 */
export function QAReviewInterface() {
  const theme = useCurrentTheme()
  const agentInfo = AGENT_DEFINITIONS.find(a => a.number === 6)

  const {
    qaReview,
    qaSelections,
    setQASelection,
    submitQAApproval,
    sopDocument,
    isProcessing,
    error,
  } = useWorkflowStore()

  // Local state
  const [selectedRecommendation, setSelectedRecommendation] = useState<string | null>(null)
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['scores', 'recommendations']))
  const [textSelection, setTextSelection] = useState<TextSelection | null>(null)
  const [comments, setComments] = useState<Comment[]>([])
  const [viewMode, setViewMode] = useState<'split' | 'preview' | 'review'>('split')

  // Calculate which recommendations have been addressed
  const addressedRecommendations = useMemo(() => {
    return new Set(qaSelections.map(s => s.recommendationId))
  }, [qaSelections])

  const allRecommendationsAddressed = useMemo(() => {
    if (!qaReview) return false
    return qaReview.recommendations.every(r => addressedRecommendations.has(r.id))
  }, [qaReview, addressedRecommendations])

  // Toggle section expansion
  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const newSet = new Set(prev)
      if (newSet.has(section)) {
        newSet.delete(section)
      } else {
        newSet.add(section)
      }
      return newSet
    })
  }

  // Handle recommendation option selection
  const handleOptionSelect = (recommendationId: string, optionValue: string) => {
    setQASelection({
      recommendationId,
      selectedOption: optionValue,
    })
  }

  // Handle text selection from document preview
  const handleTextSelect = (selection: TextSelection) => {
    setTextSelection(selection)
  }

  // Handle annotation actions
  const handleComment = (text: string, comment: string) => {
    const newComment: Comment = {
      id: `comment-${Date.now()}`,
      type: 'comment',
      selectedText: text,
      content: comment,
      author: 'User',
      timestamp: new Date(),
      sectionId: textSelection?.sectionId,
      status: 'pending',
      replies: [],
    }
    setComments(prev => [...prev, newComment])
    setTextSelection(null)
  }

  const handleSuggestEdit = (text: string, suggestion: string) => {
    const newComment: Comment = {
      id: `edit-${Date.now()}`,
      type: 'edit',
      selectedText: text,
      content: suggestion,
      author: 'User',
      timestamp: new Date(),
      sectionId: textSelection?.sectionId,
      status: 'pending',
      replies: [],
    }
    setComments(prev => [...prev, newComment])
    setTextSelection(null)
  }

  const handleFlag = (text: string, reason: string) => {
    const newComment: Comment = {
      id: `flag-${Date.now()}`,
      type: 'flag',
      selectedText: text,
      content: reason,
      author: 'User',
      timestamp: new Date(),
      sectionId: textSelection?.sectionId,
      status: 'pending',
      replies: [],
    }
    setComments(prev => [...prev, newComment])
    setTextSelection(null)
  }

  // Get severity icon and color
  const getSeverityInfo = (severity: 'critical' | 'high' | 'medium' | 'low') => {
    switch (severity) {
      case 'critical':
        return { icon: <AlertCircle size={16} />, color: theme.colors.error }
      case 'high':
        return { icon: <AlertTriangle size={16} />, color: theme.colors.warning }
      case 'medium':
        return { icon: <Info size={16} />, color: theme.colors.info }
      case 'low':
        return { icon: <Info size={16} />, color: theme.colors.gray }
    }
  }

  // Get score color
  const getScoreColor = (score: number) => {
    if (score >= 90) return theme.colors.success
    if (score >= 70) return theme.colors.warning
    return theme.colors.error
  }

  // Render star rating
  const renderStars = (score: number) => {
    const fullStars = Math.floor(score / 20)
    return (
      <div className="flex gap-0.5">
        {[...Array(5)].map((_, i) => (
          <Star
            key={i}
            size={16}
            fill={i < fullStars ? theme.colors.warning : 'transparent'}
            style={{ color: i < fullStars ? theme.colors.warning : theme.colors.border }}
          />
        ))}
      </div>
    )
  }

  // Demo data if no QA review loaded
  const demoQAReview = qaReview || {
    overallScore: 92,
    scores: {
      regulatoryCompliance: 100,
      internalConsistency: 95,
      completeness: 85,
    },
    recommendations: [
      {
        id: 'rec-1',
        section: '3.2',
        severity: 'medium' as const,
        title: 'Missing acceptance criteria',
        description: 'Section 3.2 lacks specific acceptance criteria for quality control testing.',
        options: [
          { value: 'add-cannabinoid', label: 'Add cannabinoid ranges', description: 'Include specific THC/CBD thresholds', impact: 'Improves regulatory compliance' },
          { value: 'add-microbial', label: 'Add microbial limits', description: 'Include CFU/g specifications', impact: 'Enhances product safety' },
          { value: 'skip', label: 'Skip (continue without)', description: 'Leave as is', impact: 'May require revision later' },
        ],
      },
      {
        id: 'rec-2',
        section: '4.1',
        severity: 'low' as const,
        title: 'Cross-reference update needed',
        description: 'Reference to QC_01.02 is outdated.',
        options: [
          { value: 'update', label: 'Update to QC_01.03', description: 'Use the latest version', impact: 'Ensures document accuracy' },
          { value: 'remove', label: 'Remove reference', description: 'Delete the reference entirely', impact: 'Simplifies document' },
        ],
      },
    ],
    gaps: [
      {
        section: '5.0',
        requirement: 'Training record retention period',
        source: 'EU GMP Annex 15',
        severity: 'medium' as const,
      },
    ],
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div
        className="shrink-0 px-6 py-4 border-b flex items-center justify-between"
        style={{ borderColor: theme.colors.border }}
      >
        <div className="flex items-center gap-4">
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
            style={{ backgroundColor: `${theme.colors.primary}20` }}
          >
            {agentInfo?.icon}
          </div>
          <div>
            <h1 className="text-xl font-bold" style={{ color: theme.colors.primary }}>
              Agent 6: {agentInfo?.name}
            </h1>
            <p className="text-sm" style={{ color: theme.colors.gray }}>
              {agentInfo?.description}
            </p>
          </div>
        </div>

        {/* View Mode Toggle */}
        <div
          className="flex rounded-lg overflow-hidden"
          style={{ backgroundColor: theme.colors.border }}
        >
          {(['split', 'preview', 'review'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className="px-4 py-2 text-sm font-medium transition-colors capitalize"
              style={{
                backgroundColor: viewMode === mode ? theme.colors.primary : 'transparent',
                color: viewMode === mode ? '#fff' : theme.colors.gray,
              }}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mx-6 mt-4 p-4 rounded-lg flex items-start gap-3"
          style={{
            backgroundColor: `${theme.colors.error}20`,
            borderLeft: `3px solid ${theme.colors.error}`,
          }}
        >
          <AlertCircle size={20} style={{ color: theme.colors.error }} />
          <p style={{ color: theme.colors.error }}>{error}</p>
        </motion.div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Document Preview */}
        {(viewMode === 'split' || viewMode === 'preview') && (
          <div
            className={`${viewMode === 'split' ? 'w-1/2' : 'w-full'} border-r flex flex-col`}
            style={{ borderColor: theme.colors.border }}
          >
            <DocumentPreview
              documentUrl={sopDocument?.previewUrl}
              title="SOP Document Preview"
              enableSelection={true}
              onTextSelect={handleTextSelect}
              height="100%"
              showDownload={true}
              downloadFilename={sopDocument?.filename || 'sop-document.docx'}
            />

            {/* Annotation Toolbar */}
            <AnnotationToolbar
              selection={textSelection}
              onComment={handleComment}
              onSuggestEdit={handleSuggestEdit}
              onFlag={handleFlag}
              onClose={() => setTextSelection(null)}
            />
          </div>
        )}

        {/* Right Panel - QA Review */}
        {(viewMode === 'split' || viewMode === 'review') && (
          <div
            className={`${viewMode === 'split' ? 'w-1/2' : 'w-full'} flex flex-col overflow-hidden`}
            style={{ backgroundColor: `${theme.colors.darkBg}50` }}
          >
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Quality Score Card */}
              <div
                className="rounded-xl p-6"
                style={{
                  backgroundColor: theme.colors.lightBg,
                  border: `1px solid ${theme.colors.border}`,
                }}
              >
                <button
                  onClick={() => toggleSection('scores')}
                  className="w-full flex items-center justify-between"
                >
                  <div className="flex items-center gap-3">
                    <FileCheck size={20} style={{ color: theme.colors.primary }} />
                    <span className="font-semibold" style={{ color: '#fff' }}>
                      Quality Review Report
                    </span>
                  </div>
                  <ChevronDown
                    size={18}
                    className={`transition-transform ${expandedSections.has('scores') ? 'rotate-180' : ''}`}
                    style={{ color: theme.colors.gray }}
                  />
                </button>

                <AnimatePresence>
                  {expandedSections.has('scores') && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="mt-6">
                        {/* Overall Score */}
                        <div className="text-center mb-6">
                          <div
                            className="text-5xl font-bold mb-2"
                            style={{ color: getScoreColor(demoQAReview.overallScore) }}
                          >
                            {demoQAReview.overallScore}
                          </div>
                          <p className="text-sm mb-2" style={{ color: theme.colors.gray }}>
                            Overall Score
                          </p>
                          {renderStars(demoQAReview.overallScore)}
                        </div>

                        {/* Individual Scores */}
                        <div className="space-y-4">
                          {Object.entries(demoQAReview.scores).map(([key, value]) => {
                            const label = key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())
                            const scoreColor = getScoreColor(value)
                            const icon = value >= 90 ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />

                            return (
                              <div key={key} className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <span style={{ color: scoreColor }}>{icon}</span>
                                  <span className="text-sm" style={{ color: theme.colors.gray }}>
                                    {label}
                                  </span>
                                </div>
                                <div className="flex items-center gap-3">
                                  <div
                                    className="w-32 h-2 rounded-full overflow-hidden"
                                    style={{ backgroundColor: theme.colors.border }}
                                  >
                                    <div
                                      className="h-full transition-all"
                                      style={{
                                        width: `${value}%`,
                                        backgroundColor: scoreColor,
                                      }}
                                    />
                                  </div>
                                  <span
                                    className="text-sm font-semibold w-10"
                                    style={{ color: scoreColor }}
                                  >
                                    {value}%
                                  </span>
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Recommendations */}
              <div
                className="rounded-xl p-6"
                style={{
                  backgroundColor: theme.colors.lightBg,
                  border: `1px solid ${theme.colors.border}`,
                }}
              >
                <button
                  onClick={() => toggleSection('recommendations')}
                  className="w-full flex items-center justify-between"
                >
                  <div className="flex items-center gap-3">
                    <Sparkles size={20} style={{ color: theme.colors.accent }} />
                    <span className="font-semibold" style={{ color: '#fff' }}>
                      Recommendations ({demoQAReview.recommendations.length})
                    </span>
                    <span
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{
                        backgroundColor: allRecommendationsAddressed
                          ? `${theme.colors.success}20`
                          : `${theme.colors.warning}20`,
                        color: allRecommendationsAddressed
                          ? theme.colors.success
                          : theme.colors.warning,
                      }}
                    >
                      {addressedRecommendations.size}/{demoQAReview.recommendations.length} addressed
                    </span>
                  </div>
                  <ChevronDown
                    size={18}
                    className={`transition-transform ${expandedSections.has('recommendations') ? 'rotate-180' : ''}`}
                    style={{ color: theme.colors.gray }}
                  />
                </button>

                <AnimatePresence>
                  {expandedSections.has('recommendations') && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="mt-6 space-y-4">
                        {demoQAReview.recommendations.map((rec, index) => {
                          const severityInfo = getSeverityInfo(rec.severity)
                          const isExpanded = selectedRecommendation === rec.id
                          const isAddressed = addressedRecommendations.has(rec.id)
                          const selection = qaSelections.find(s => s.recommendationId === rec.id)

                          return (
                            <div
                              key={rec.id}
                              className="rounded-lg overflow-hidden"
                              style={{
                                backgroundColor: `${theme.colors.darkBg}80`,
                                border: `1px solid ${isAddressed ? theme.colors.success : theme.colors.border}`,
                              }}
                            >
                              <button
                                onClick={() => setSelectedRecommendation(isExpanded ? null : rec.id)}
                                className="w-full p-4 flex items-start gap-3 text-left"
                              >
                                <div
                                  className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                                  style={{
                                    backgroundColor: `${severityInfo.color}20`,
                                    color: severityInfo.color,
                                  }}
                                >
                                  {isAddressed ? <Check size={16} /> : severityInfo.icon}
                                </div>
                                <div className="flex-1">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="font-medium" style={{ color: '#fff' }}>
                                      {index + 1}. {rec.title}
                                    </span>
                                    <span
                                      className="text-xs px-2 py-0.5 rounded"
                                      style={{
                                        backgroundColor: `${severityInfo.color}20`,
                                        color: severityInfo.color,
                                      }}
                                    >
                                      {rec.severity}
                                    </span>
                                  </div>
                                  <p className="text-sm" style={{ color: theme.colors.gray }}>
                                    Section {rec.section}
                                  </p>
                                </div>
                                <ChevronRight
                                  size={18}
                                  className={`transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                                  style={{ color: theme.colors.gray }}
                                />
                              </button>

                              <AnimatePresence>
                                {isExpanded && (
                                  <motion.div
                                    initial={{ height: 0 }}
                                    animate={{ height: 'auto' }}
                                    exit={{ height: 0 }}
                                    className="overflow-hidden"
                                  >
                                    <div className="px-4 pb-4">
                                      <p
                                        className="text-sm mb-4"
                                        style={{ color: theme.colors.gray }}
                                      >
                                        {rec.description}
                                      </p>

                                      {/* Options */}
                                      <div className="space-y-2">
                                        {rec.options.map((option) => {
                                          const isSelected = selection?.selectedOption === option.value

                                          return (
                                            <button
                                              key={option.value}
                                              onClick={() => handleOptionSelect(rec.id, option.value)}
                                              className="w-full p-3 rounded-lg border text-left transition-all"
                                              style={{
                                                backgroundColor: isSelected
                                                  ? `${theme.colors.primary}20`
                                                  : 'transparent',
                                                borderColor: isSelected
                                                  ? theme.colors.primary
                                                  : theme.colors.border,
                                              }}
                                            >
                                              <div className="flex items-start gap-3">
                                                <div
                                                  className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5`}
                                                  style={{
                                                    borderColor: isSelected
                                                      ? theme.colors.primary
                                                      : theme.colors.border,
                                                    backgroundColor: isSelected
                                                      ? theme.colors.primary
                                                      : 'transparent',
                                                  }}
                                                >
                                                  {isSelected && <Check size={10} color="#fff" />}
                                                </div>
                                                <div>
                                                  <p
                                                    className="font-medium text-sm"
                                                    style={{ color: '#fff' }}
                                                  >
                                                    {option.label}
                                                  </p>
                                                  <p
                                                    className="text-xs mt-0.5"
                                                    style={{ color: theme.colors.gray }}
                                                  >
                                                    {option.description}
                                                  </p>
                                                  <p
                                                    className="text-xs mt-1"
                                                    style={{ color: theme.colors.info }}
                                                  >
                                                    Impact: {option.impact}
                                                  </p>
                                                </div>
                                              </div>
                                            </button>
                                          )
                                        })}
                                      </div>
                                    </div>
                                  </motion.div>
                                )}
                              </AnimatePresence>
                            </div>
                          )
                        })}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* User Comments */}
              {comments.length > 0 && (
                <div
                  className="rounded-xl p-6"
                  style={{
                    backgroundColor: theme.colors.lightBg,
                    border: `1px solid ${theme.colors.border}`,
                  }}
                >
                  <h3
                    className="font-semibold mb-4 flex items-center gap-2"
                    style={{ color: '#fff' }}
                  >
                    Your Annotations ({comments.length})
                  </h3>
                  <CommentThread
                    comments={comments}
                    onResolve={(id) => setComments(prev => prev.map(c => c.id === id ? { ...c, status: 'resolved' } : c))}
                    onReject={(id) => setComments(prev => prev.map(c => c.id === id ? { ...c, status: 'rejected' } : c))}
                    onDelete={(id) => setComments(prev => prev.filter(c => c.id !== id))}
                    onReply={(id, content) => setComments(prev => prev.map(c => c.id === id ? { ...c, replies: [...c.replies, { id: `reply-${Date.now()}`, content, author: 'Agent', timestamp: new Date(), isAgentResponse: true }] } : c))}
                  />
                </div>
              )}
            </div>

            {/* Footer Actions */}
            <div
              className="shrink-0 p-4 border-t flex items-center justify-between"
              style={{
                backgroundColor: theme.colors.lightBg,
                borderColor: theme.colors.border,
              }}
            >
              <div className="text-sm" style={{ color: theme.colors.gray }}>
                {allRecommendationsAddressed
                  ? 'All recommendations addressed'
                  : `${demoQAReview.recommendations.length - addressedRecommendations.size} recommendations remaining`}
              </div>
              <button
                onClick={submitQAApproval}
                disabled={!allRecommendationsAddressed || isProcessing}
                className="flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all disabled:opacity-50"
                style={{
                  background: allRecommendationsAddressed
                    ? `linear-gradient(135deg, ${theme.colors.primary}, ${theme.colors.secondary})`
                    : theme.colors.border,
                  color: '#fff',
                  boxShadow: allRecommendationsAddressed
                    ? `0 4px 15px ${theme.colors.primary}40`
                    : 'none',
                }}
              >
                {isProcessing ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <Check size={18} />
                    Approve & Generate Document
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default QAReviewInterface
