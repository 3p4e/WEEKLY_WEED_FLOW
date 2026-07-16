import { CheckCircle, AlertCircle, Lightbulb, TrendingUp } from 'lucide-react'
import { useState } from 'react'
import { useCurrentTheme } from '../../context/ThemeContext'

export interface QualityChecklistItem {
  id: string
  category: string
  title: string
  status: 'pass' | 'warning' | 'fail'
  message: string
}

export interface QualityRecommendation {
  id: string
  priority: 'high' | 'medium' | 'low'
  title: string
  description: string
  options?: string[]
  selectedOption?: string
}

export interface QualityReviewProps {
  score: number // 0-100
  checklist: QualityChecklistItem[]
  recommendations: QualityRecommendation[]
  onRecommendationUpdate?: (recommendationId: string, selectedOption: string) => void
  onApprove?: () => void
}

/**
 * QualityReview Component
 * Displays Quality Assembler (Agent 6) assessment and recommendations
 * Shows compliance score, checklist status, and suggested improvements
 */
export function QualityReview({
  score,
  checklist,
  recommendations,
  onRecommendationUpdate,
  onApprove,
}: QualityReviewProps) {
  const theme = useCurrentTheme()
  const [expandedRecommendation, setExpandedRecommendation] = useState<string | null>(null)

  const getScoreColor = (s: number) => {
    if (s >= 90) return theme.colors.success
    if (s >= 70) return theme.colors.warning
    return theme.colors.error
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pass':
        return <CheckCircle size={16} style={{ color: theme.colors.success }} />
      case 'warning':
        return <AlertCircle size={16} style={{ color: theme.colors.warning }} />
      case 'fail':
        return <AlertCircle size={16} style={{ color: theme.colors.error }} />
      default:
        return null
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high':
        return theme.colors.error
      case 'medium':
        return theme.colors.warning
      case 'low':
        return theme.colors.info
      default:
        return theme.colors.gray
    }
  }

  const categorized = checklist.reduce(
    (acc, item) => {
      if (!acc[item.category]) acc[item.category] = []
      acc[item.category].push(item)
      return acc
    },
    {} as Record<string, QualityChecklistItem[]>
  )

  return (
    <div className="space-y-6">
      {/* Quality Score Card */}
      <div
        className="rounded-lg border p-6"
        style={{
          backgroundColor: theme.colors.lightBg,
          borderColor: theme.colors.border,
        }}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2
              className="text-lg font-semibold mb-1"
              style={{ color: theme.colors.primary }}
            >
              Quality Assessment
            </h2>
            <p className="text-sm" style={{ color: theme.colors.gray }}>
              Reviewed by Quality Assembler Agent
            </p>
          </div>
          <div className="text-right">
            <div
              className="text-5xl font-bold"
              style={{ color: getScoreColor(score) }}
            >
              {score}
            </div>
            <p
              className="text-xs font-semibold mt-1"
              style={{ color: theme.colors.gray }}
            >
              / 100
            </p>
          </div>
        </div>

        {/* Score Interpretation */}
        <div
          className="p-3 rounded-lg"
          style={{
            backgroundColor: `${getScoreColor(score)}15`,
            borderLeft: `4px solid ${getScoreColor(score)}`,
          }}
        >
          <p style={{ color: getScoreColor(score) }} className="text-sm font-medium">
            {score >= 90
              ? '✓ Excellent - Document meets all quality standards'
              : score >= 70
              ? '⚠ Good - Document meets standards with minor suggestions'
              : '✗ Needs Review - Document requires attention'}
          </p>
        </div>
      </div>

      {/* Compliance Checklist */}
      <div
        className="rounded-lg border p-6"
        style={{
          backgroundColor: theme.colors.lightBg,
          borderColor: theme.colors.border,
        }}
      >
        <h3
          className="text-lg font-semibold mb-4 flex items-center gap-2"
          style={{ color: theme.colors.primary }}
        >
          <TrendingUp size={20} />
          Compliance Checklist
        </h3>

        {Object.entries(categorized).map(([category, items]) => (
          <div key={category} className="mb-5 last:mb-0">
            <h4
              className="text-sm font-semibold mb-3"
              style={{ color: theme.colors.secondary }}
            >
              {category}
            </h4>
            <div className="space-y-2">
              {items.map((item) => (
                <div
                  key={item.id}
                  className="flex items-start gap-3 p-3 rounded-lg"
                  style={{
                    backgroundColor: `${getPriorityColor(item.status)}08`,
                  }}
                >
                  <div className="mt-0.5 shrink-0">{getStatusIcon(item.status)}</div>
                  <div className="flex-1 min-w-0">
                    <p
                      className="text-sm font-medium"
                      style={{ color: theme.colors.gray }}
                    >
                      {item.title}
                    </p>
                    <p
                      className="text-xs mt-1"
                      style={{ color: `${theme.colors.gray}80` }}
                    >
                      {item.message}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div
          className="rounded-lg border p-6"
          style={{
            backgroundColor: theme.colors.lightBg,
            borderColor: theme.colors.border,
          }}
        >
          <h3
            className="text-lg font-semibold mb-4 flex items-center gap-2"
            style={{ color: theme.colors.primary }}
          >
            <Lightbulb size={20} />
            Recommendations ({recommendations.length})
          </h3>

          <div className="space-y-3">
            {recommendations.map((rec) => (
              <div
                key={rec.id}
                className="border rounded-lg overflow-hidden"
                style={{
                  borderColor: `${getPriorityColor(rec.priority)}40`,
                  backgroundColor: `${getPriorityColor(rec.priority)}05`,
                }}
              >
                <button
                  onClick={() =>
                    setExpandedRecommendation(
                      expandedRecommendation === rec.id ? null : rec.id
                    )
                  }
                  className="w-full text-left p-4 flex items-start justify-between hover:opacity-80 transition-opacity"
                >
                  <div className="flex items-start gap-3 flex-1">
                    <div
                      className="px-2 py-1 rounded text-xs font-semibold mt-0.5 whitespace-nowrap"
                      style={{
                        backgroundColor: getPriorityColor(rec.priority),
                        color: 'white',
                      }}
                    >
                      {rec.priority.toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p
                        className="font-semibold"
                        style={{ color: theme.colors.primary }}
                      >
                        {rec.title}
                      </p>
                    </div>
                  </div>
                  <div
                    className="text-sm ml-2 shrink-0"
                    style={{ color: theme.colors.gray }}
                  >
                    {expandedRecommendation === rec.id ? '▼' : '▶'}
                  </div>
                </button>

                {expandedRecommendation === rec.id && (
                  <div
                    className="px-4 pb-4 pt-0 border-t"
                    style={{ borderTopColor: `${getPriorityColor(rec.priority)}40` }}
                  >
                    <p
                      className="text-sm mb-3"
                      style={{ color: theme.colors.gray }}
                    >
                      {rec.description}
                    </p>

                    {rec.options && rec.options.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs font-semibold" style={{ color: theme.colors.gray }}>
                          How would you like to proceed?
                        </p>
                        {rec.options.map((option) => (
                          <label
                            key={option}
                            className="flex items-center gap-2 p-2 rounded cursor-pointer hover:opacity-80 transition-opacity"
                            style={{
                              backgroundColor: `${theme.colors.primary}10`,
                            }}
                          >
                            <input
                              type="radio"
                              name={`rec-${rec.id}`}
                              value={option}
                              checked={rec.selectedOption === option}
                              onChange={() =>
                                onRecommendationUpdate?.(rec.id, option)
                              }
                              className="w-4 h-4 cursor-pointer"
                            />
                            <span
                              className="text-sm"
                              style={{ color: theme.colors.gray }}
                            >
                              {option}
                            </span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Buttons */}
      {onApprove && (
        <button
          onClick={onApprove}
          className="w-full py-3 rounded-lg font-semibold text-white transition-opacity hover:opacity-90"
          style={{ backgroundColor: theme.colors.success }}
        >
          Approve & Generate Document
        </button>
      )}
    </div>
  )
}
