import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronLeft,
  ChevronRight,
  BookOpen,
  Flag,
  Check,
  Circle,
  AlertCircle,
  Database,
  Sparkles,
  HelpCircle,
  ChevronDown,
  Loader2,
} from 'lucide-react'
import { useCurrentTheme } from '../../context/ThemeContext'
import { useWorkflowStore } from '../../stores/useWorkflowStore'
import type {
  AgentNumber,
  RAGContext,
} from '../../types/workflow'
import { AGENT_DEFINITIONS } from '../../types/workflow'

interface QuestionnaireViewProps {
  agentNumber: AgentNumber
}

/**
 * QuestionnaireView Component
 * Interactive questionnaire interface for Agents 2, 3, and 8
 * Features: Single question view, RAG context panel, navigation, mark for review
 */
export function QuestionnaireView({ agentNumber }: QuestionnaireViewProps) {
  const theme = useCurrentTheme()
  const agentInfo = AGENT_DEFINITIONS.find(a => a.number === agentNumber)

  // Get store data based on agent number
  const {
    introQuestions,
    introAnswers,
    procedureQuestions,
    procedureAnswers,
    annexQuestionnaires,
    answerIntroQuestion,
    answerProcedureQuestion,
    answerAnnexQuestion,
    submitIntroAnswers,
    submitProcedureAnswers,
    submitAnnexAnswers,
    isProcessing,
    error,
  } = useWorkflowStore()

  // Select questions and answers based on agent
  const questions = useMemo(() => {
    switch (agentNumber) {
      case 2:
        return introQuestions
      case 3:
        return procedureQuestions
      case 8: {
        // For annexes, we need to get the current annex questions
        const annexIds = Object.keys(annexQuestionnaires)
        if (annexIds.length > 0) {
          return annexQuestionnaires[annexIds[0]]?.questions || []
        }
        return []
      }
      default:
        return []
    }
  }, [agentNumber, introQuestions, procedureQuestions, annexQuestionnaires])

  const answers = useMemo(() => {
    switch (agentNumber) {
      case 2:
        return introAnswers
      case 3:
        return procedureAnswers
      case 8: {
        const annexIds = Object.keys(annexQuestionnaires)
        if (annexIds.length > 0) {
          return annexQuestionnaires[annexIds[0]]?.answers || []
        }
      }
        return []
      default:
        return []
    }
  }, [agentNumber, introAnswers, procedureAnswers, annexQuestionnaires])

  // Local state
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0)
  const [markedForReview, setMarkedForReview] = useState<Set<string>>(new Set())
  const [showRAGContext, setShowRAGContext] = useState(false)
  const [showSidebar, setShowSidebar] = useState(true)

  const currentQuestion = questions[currentQuestionIndex]

  // Get answer for current question
  const getCurrentAnswer = () => {
    if (!currentQuestion) return null
    const response = answers.find(a => a.questionId === currentQuestion.id)
    return response?.answer || null
  }

  // Handle answer selection
  const handleAnswer = (answer: string | string[]) => {
    if (!currentQuestion) return

    switch (agentNumber) {
      case 2:
        answerIntroQuestion(currentQuestion.id, answer)
        break
      case 3:
        answerProcedureQuestion(currentQuestion.id, answer)
        break
      case 8: {
        const annexIds = Object.keys(annexQuestionnaires)
        if (annexIds.length > 0) {
          answerAnnexQuestion(annexIds[0], currentQuestion.id, answer)
        }
      }
        break
    }
  }

  // Handle single option selection
  const handleOptionSelect = (optionValue: string) => {
    if (currentQuestion?.type === 'multiple_choice') {
      const currentAnswer = getCurrentAnswer()
      const currentSelections = Array.isArray(currentAnswer) ? currentAnswer : []
      const newSelections = currentSelections.includes(optionValue)
        ? currentSelections.filter(v => v !== optionValue)
        : [...currentSelections, optionValue]
      handleAnswer(newSelections)
    } else {
      handleAnswer(optionValue)
    }
  }

  // Navigation
  const goToNext = () => {
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(prev => prev + 1)
    }
  }

  const goToPrevious = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(prev => prev - 1)
    }
  }

  // Toggle mark for review
  const toggleReviewMark = () => {
    if (!currentQuestion) return
    setMarkedForReview(prev => {
      const newSet = new Set(prev)
      if (newSet.has(currentQuestion.id)) {
        newSet.delete(currentQuestion.id)
      } else {
        newSet.add(currentQuestion.id)
      }
      return newSet
    })
  }

  // Submit questionnaire
  const handleSubmit = async () => {
    switch (agentNumber) {
      case 2:
        await submitIntroAnswers()
        break
      case 3:
        await submitProcedureAnswers()
        break
      case 8: {
        const annexIds = Object.keys(annexQuestionnaires)
        if (annexIds.length > 0) {
          await submitAnnexAnswers(annexIds[0])
        }
      }
        break
    }
  }

  // Calculate progress
  const answeredCount = answers.length
  const progressPercentage = questions.length > 0 ? (answeredCount / questions.length) * 100 : 0
  const canSubmit = answeredCount === questions.length && questions.length > 0

  // Check if option is selected
  const isOptionSelected = (optionValue: string) => {
    const answer = getCurrentAnswer()
    if (Array.isArray(answer)) {
      return answer.includes(optionValue)
    }
    return answer === optionValue
  }

  if (questions.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Loader2
            size={40}
            className="animate-spin mx-auto mb-4"
            style={{ color: theme.colors.primary }}
          />
          <p style={{ color: theme.colors.gray }}>Loading questions...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-[600px]">
      {/* Left Sidebar - Question Navigator */}
      <AnimatePresence>
        {showSidebar && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 240, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            className="shrink-0 border-r overflow-hidden"
            style={{
              backgroundColor: `${theme.colors.lightBg}50`,
              borderColor: theme.colors.border,
            }}
          >
            <div className="p-4 h-full flex flex-col">
              {/* Sidebar Header */}
              <div className="mb-4">
                <h3
                  className="text-sm font-semibold mb-1"
                  style={{ color: theme.colors.primary }}
                >
                  Questions
                </h3>
                <p className="text-xs" style={{ color: theme.colors.gray }}>
                  {answeredCount}/{questions.length} completed
                </p>
                <div
                  className="h-1 rounded-full mt-2 overflow-hidden"
                  style={{ backgroundColor: theme.colors.border }}
                >
                  <div
                    className="h-full transition-all"
                    style={{
                      width: `${progressPercentage}%`,
                      backgroundColor: theme.colors.success,
                    }}
                  />
                </div>
              </div>

              {/* Question List */}
              <div className="flex-1 overflow-y-auto space-y-1">
                {questions.map((q, index) => {
                  const isAnswered = answers.some(a => a.questionId === q.id)
                  const isCurrent = index === currentQuestionIndex
                  const isMarked = markedForReview.has(q.id)

                  return (
                    <button
                      key={q.id}
                      onClick={() => setCurrentQuestionIndex(index)}
                      className="w-full text-left px-3 py-2 rounded-lg flex items-center gap-2 transition-all"
                      style={{
                        backgroundColor: isCurrent
                          ? `${theme.colors.primary}20`
                          : 'transparent',
                        borderLeft: isCurrent
                          ? `3px solid ${theme.colors.primary}`
                          : '3px solid transparent',
                      }}
                    >
                      {/* Status Icon */}
                      <div className="shrink-0">
                        {isMarked ? (
                          <Flag size={14} style={{ color: theme.colors.warning }} />
                        ) : isAnswered ? (
                          <Check size={14} style={{ color: theme.colors.success }} />
                        ) : (
                          <Circle size={14} style={{ color: theme.colors.border }} />
                        )}
                      </div>
                      <span
                        className="text-sm truncate"
                        style={{
                          color: isCurrent ? theme.colors.primary : theme.colors.gray,
                        }}
                      >
                        Q{index + 1}
                      </span>
                    </button>
                  )
                })}
              </div>

              {/* Sidebar Footer */}
              {markedForReview.size > 0 && (
                <div
                  className="mt-4 p-2 rounded-lg text-xs"
                  style={{
                    backgroundColor: `${theme.colors.warning}20`,
                    color: theme.colors.warning,
                  }}
                >
                  <Flag size={12} className="inline mr-1" />
                  {markedForReview.size} marked for review
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div
          className="p-4 border-b flex items-center justify-between"
          style={{ borderColor: theme.colors.border }}
        >
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className="p-2 rounded-lg transition-colors"
              style={{
                backgroundColor: showSidebar ? `${theme.colors.primary}20` : 'transparent',
                color: theme.colors.gray,
              }}
            >
              <ChevronLeft size={18} />
            </button>
            <div>
              <h1
                className="text-lg font-semibold"
                style={{ color: theme.colors.primary }}
              >
                Agent {agentNumber}: {agentInfo?.name}
              </h1>
              <p className="text-sm" style={{ color: theme.colors.gray }}>
                {agentInfo?.description}
              </p>
            </div>
          </div>
          <div
            className="px-3 py-1 rounded-lg text-sm"
            style={{
              backgroundColor: `${theme.colors.secondary}20`,
              color: theme.colors.secondary,
            }}
          >
            Question {currentQuestionIndex + 1} of {questions.length}
          </div>
        </div>

        {/* Question Card */}
        <div className="flex-1 overflow-y-auto p-6">
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
              <p style={{ color: theme.colors.error }}>{error}</p>
            </motion.div>
          )}

          {currentQuestion && (
            <motion.div
              key={currentQuestion.id}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="max-w-3xl mx-auto"
            >
              {/* Question Header */}
              <div
                className="p-6 rounded-t-xl"
                style={{
                  backgroundColor: `${theme.colors.primary}10`,
                  borderBottom: `1px solid ${theme.colors.border}`,
                }}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span
                        className="px-2 py-0.5 rounded text-xs font-semibold"
                        style={{
                          backgroundColor: `${theme.colors.primary}30`,
                          color: theme.colors.primary,
                        }}
                      >
                        Q{currentQuestionIndex + 1}
                      </span>
                      <span
                        className="text-xs"
                        style={{ color: theme.colors.gray }}
                      >
                        {currentQuestion.type === 'multiple_choice'
                          ? 'Select all that apply'
                          : currentQuestion.type === 'text'
                          ? 'Enter your response'
                          : currentQuestion.options?.length > 0
                          ? 'Select one option'
                          : 'Enter your response'}
                      </span>
                      {currentQuestion.required && (
                        <span
                          className="text-xs px-2 py-0.5 rounded"
                          style={{
                            backgroundColor: `${theme.colors.error}20`,
                            color: theme.colors.error,
                          }}
                        >
                          Required
                        </span>
                      )}
                    </div>
                    <h2
                      className="text-xl font-semibold"
                      style={{ color: '#fff' }}
                    >
                      {currentQuestion.text}
                    </h2>
                    {currentQuestion.helpText && (
                      <p
                        className="mt-2 text-sm"
                        style={{ color: theme.colors.gray }}
                      >
                        {currentQuestion.helpText}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={toggleReviewMark}
                    className="p-2 rounded-lg transition-colors shrink-0"
                    style={{
                      backgroundColor: markedForReview.has(currentQuestion.id)
                        ? `${theme.colors.warning}20`
                        : 'transparent',
                      color: markedForReview.has(currentQuestion.id)
                        ? theme.colors.warning
                        : theme.colors.gray,
                    }}
                    title="Mark for review"
                  >
                    <Flag size={20} />
                  </button>
                </div>
              </div>

              {/* Options or Text Input */}
              <div
                className="p-6 rounded-b-xl"
                style={{
                  backgroundColor: theme.colors.lightBg,
                  border: `1px solid ${theme.colors.border}`,
                  borderTop: 'none',
                }}
              >
                {/* Text Input for text-type questions or when no options available */}
                {(currentQuestion.type === 'text' || !currentQuestion.options || currentQuestion.options.length === 0) ? (
                  <div className="space-y-3">
                    <textarea
                      value={typeof getCurrentAnswer() === 'string' ? getCurrentAnswer() as string : ''}
                      onChange={(e) => handleAnswer(e.target.value)}
                      placeholder="Enter your response here..."
                      rows={6}
                      className="w-full rounded-lg border px-4 py-3 transition-all outline-none resize-y min-h-[150px]"
                      style={{
                        backgroundColor: `${theme.colors.darkBg}50`,
                        borderColor: theme.colors.border,
                        color: '#fff',
                      }}
                      onFocus={(e) => {
                        e.target.style.borderColor = theme.colors.primary
                        e.target.style.boxShadow = `0 0 0 2px ${theme.colors.primary}30`
                      }}
                      onBlur={(e) => {
                        e.target.style.borderColor = theme.colors.border
                        e.target.style.boxShadow = 'none'
                      }}
                    />
                    <p className="text-xs" style={{ color: theme.colors.gray }}>
                      Provide a detailed response. Your answer will be used to generate the SOP content.
                    </p>
                  </div>
                ) : (
                <div className="space-y-3">
                  {currentQuestion.options.map((option) => {
                    const selected = isOptionSelected(option.value)

                    return (
                      <button
                        key={option.value}
                        onClick={() => handleOptionSelect(option.value)}
                        className="w-full text-left p-4 rounded-lg border transition-all"
                        style={{
                          backgroundColor: selected
                            ? `${theme.colors.secondary}15`
                            : `${theme.colors.darkBg}50`,
                          borderColor: selected
                            ? theme.colors.secondary
                            : theme.colors.border,
                          boxShadow: selected
                            ? `0 0 15px ${theme.colors.secondary}30`
                            : 'none',
                        }}
                      >
                        <div className="flex items-start gap-3">
                          {/* Checkbox/Radio */}
                          <div
                            className={`w-5 h-5 rounded-${
                              currentQuestion.type === 'multiple_choice' ? 'md' : 'full'
                            } border-2 flex items-center justify-center shrink-0 mt-0.5 transition-all`}
                            style={{
                              borderColor: selected
                                ? theme.colors.secondary
                                : theme.colors.border,
                              backgroundColor: selected
                                ? theme.colors.secondary
                                : 'transparent',
                            }}
                          >
                            {selected && <Check size={12} color="#fff" />}
                          </div>

                          {/* Option Content */}
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <span
                                className="font-medium"
                                style={{ color: '#fff' }}
                              >
                                {option.label}
                              </span>
                              {option.recommended && (
                                <span
                                  className="text-xs px-2 py-0.5 rounded flex items-center gap-1"
                                  style={{
                                    backgroundColor: `${theme.colors.success}20`,
                                    color: theme.colors.success,
                                  }}
                                >
                                  <Sparkles size={10} />
                                  Recommended
                                </span>
                              )}
                              {option.sourceDb && (
                                <span
                                  className="text-xs px-2 py-0.5 rounded flex items-center gap-1"
                                  style={{
                                    backgroundColor: option.sourceDb === 'DB1'
                                      ? `${theme.colors.info}20`
                                      : `${theme.colors.accent}20`,
                                    color: option.sourceDb === 'DB1'
                                      ? theme.colors.info
                                      : theme.colors.accent,
                                  }}
                                >
                                  <Database size={10} />
                                  {option.sourceDb === 'DB1' ? 'Regulatory' : 'Operational'}
                                </span>
                              )}
                            </div>
                            {option.description && (
                              <p
                                className="text-sm"
                                style={{ color: theme.colors.gray }}
                              >
                                {option.description}
                              </p>
                            )}
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>
                )}

                {/* RAG Context Toggle */}
                {currentQuestion.ragContext && (
                  <div className="mt-6">
                    <button
                      onClick={() => setShowRAGContext(!showRAGContext)}
                      className="flex items-center gap-2 text-sm transition-colors"
                      style={{ color: theme.colors.info }}
                    >
                      <HelpCircle size={16} />
                      Why these options?
                      <ChevronDown
                        size={16}
                        className={`transition-transform ${showRAGContext ? 'rotate-180' : ''}`}
                      />
                    </button>

                    <AnimatePresence>
                      {showRAGContext && (
                        <RAGContextPanel context={currentQuestion.ragContext} />
                      )}
                    </AnimatePresence>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </div>

        {/* Navigation Footer */}
        <div
          className="p-4 border-t flex items-center justify-between"
          style={{
            backgroundColor: `${theme.colors.lightBg}50`,
            borderColor: theme.colors.border,
          }}
        >
          <button
            onClick={goToPrevious}
            disabled={currentQuestionIndex === 0}
            className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all disabled:opacity-50"
            style={{
              backgroundColor: 'transparent',
              color: theme.colors.gray,
              border: `1px solid ${theme.colors.border}`,
            }}
          >
            <ChevronLeft size={18} />
            Previous
          </button>

          <div className="flex items-center gap-2">
            {/* Progress dots */}
            {questions.map((_, index) => (
              <div
                key={index}
                className="w-2 h-2 rounded-full cursor-pointer transition-all"
                onClick={() => setCurrentQuestionIndex(index)}
                style={{
                  backgroundColor:
                    index === currentQuestionIndex
                      ? theme.colors.primary
                      : answers.some(a => a.questionId === questions[index].id)
                      ? theme.colors.success
                      : theme.colors.border,
                  transform: index === currentQuestionIndex ? 'scale(1.5)' : 'scale(1)',
                }}
              />
            ))}
          </div>

          {currentQuestionIndex === questions.length - 1 ? (
            <button
              onClick={handleSubmit}
              disabled={!canSubmit || isProcessing}
              className="flex items-center gap-2 px-6 py-2 rounded-lg font-semibold transition-all disabled:opacity-50"
              style={{
                background: canSubmit
                  ? `linear-gradient(135deg, ${theme.colors.primary}, ${theme.colors.secondary})`
                  : theme.colors.border,
                color: '#fff',
                boxShadow: canSubmit ? `0 4px 15px ${theme.colors.primary}40` : 'none',
              }}
            >
              {isProcessing ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  Submit & Continue
                  <ChevronRight size={18} />
                </>
              )}
            </button>
          ) : (
            <button
              onClick={goToNext}
              className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all"
              style={{
                backgroundColor: theme.colors.primary,
                color: '#fff',
              }}
            >
              Next
              <ChevronRight size={18} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// RAG Context Panel Component
function RAGContextPanel({ context }: { context: RAGContext }) {
  const theme = useCurrentTheme()

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="mt-4 overflow-hidden"
    >
      <div
        className="p-4 rounded-lg"
        style={{
          backgroundColor: `${theme.colors.info}10`,
          border: `1px solid ${theme.colors.info}30`,
        }}
      >
        <p
          className="text-sm font-semibold mb-4"
          style={{ color: theme.colors.info }}
        >
          <BookOpen size={16} className="inline mr-2" />
          These options are derived from our knowledge databases:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* DB1 Results - Regulatory */}
          {context.db1Results.length > 0 && (
            <div>
              <h4
                className="text-xs font-semibold mb-2 flex items-center gap-1"
                style={{ color: theme.colors.info }}
              >
                <Database size={12} />
                Regulatory Database (DB1)
              </h4>
              <div className="space-y-2">
                {context.db1Results.map((result, idx) => (
                  <div
                    key={idx}
                    className="p-2 rounded text-xs"
                    style={{
                      backgroundColor: `${theme.colors.darkBg}50`,
                    }}
                  >
                    <p style={{ color: '#fff' }}>{result.text}</p>
                    <p
                      className="mt-1 font-mono"
                      style={{ color: theme.colors.gray }}
                    >
                      Source: {result.source} (Score: {(result.score * 100).toFixed(0)}%)
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* DB2 Results - Operational */}
          {context.db2Results.length > 0 && (
            <div>
              <h4
                className="text-xs font-semibold mb-2 flex items-center gap-1"
                style={{ color: theme.colors.accent }}
              >
                <Database size={12} />
                Operational Database (DB2)
              </h4>
              <div className="space-y-2">
                {context.db2Results.map((result, idx) => (
                  <div
                    key={idx}
                    className="p-2 rounded text-xs"
                    style={{
                      backgroundColor: `${theme.colors.darkBg}50`,
                    }}
                  >
                    <p style={{ color: '#fff' }}>{result.text}</p>
                    <p
                      className="mt-1 font-mono"
                      style={{ color: theme.colors.gray }}
                    >
                      Source: {result.source} (Score: {(result.score * 100).toFixed(0)}%)
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

export default QuestionnaireView
