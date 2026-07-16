import { useState } from 'react'
import { ChevronDown, BookOpen, CheckCircle, Circle } from 'lucide-react'
import { useCurrentTheme } from '../../context/ThemeContext'

export interface QuestionOption {
  id: string | number
  label: string
  description: string
  sources?: string[]
  details?: string
}

export interface QuestionCardProps {
  questionNumber: number
  title: string
  description?: string
  options: QuestionOption[]
  multiSelect?: boolean
  selectedOptions?: (string | number)[]
  onSelect: (optionId: string | number) => void
  onMultiSelect?: (optionIds: (string | number)[]) => void
}

/**
 * QuestionCard Component
 * Displays a question with multiple choice options derived from database queries
 * Supports single and multi-select modes
 * Includes expandable source citations
 */
export function QuestionCard({
  questionNumber,
  title,
  description,
  options,
  multiSelect = false,
  selectedOptions = [],
  onSelect,
  onMultiSelect,
}: QuestionCardProps) {
  const theme = useCurrentTheme()
  const [expandedSource, setExpandedSource] = useState<string | number | null>(null)

  const handleOptionClick = (optionId: string | number) => {
    if (multiSelect && onMultiSelect) {
      if (selectedOptions.includes(optionId)) {
        onMultiSelect(selectedOptions.filter((id) => id !== optionId))
      } else {
        onMultiSelect([...selectedOptions, optionId])
      }
    } else {
      onSelect(optionId)
    }
  }

  const isOptionSelected = (optionId: string | number) => {
    return selectedOptions.includes(optionId)
  }

  return (
    <div
      className="rounded-lg border p-6 mb-6"
      style={{
        backgroundColor: theme.colors.lightBg,
        borderColor: theme.colors.border,
      }}
    >
      {/* Question Header */}
      <div className="mb-5">
        <div className="flex items-start gap-3 mb-2">
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 font-semibold text-white"
            style={{ backgroundColor: theme.colors.primary }}
          >
            {questionNumber}
          </div>
          <div className="flex-1">
            <h2
              className="text-lg font-semibold mb-1"
              style={{ color: theme.colors.primary }}
            >
              {title}
            </h2>
            {description && (
              <p
                className="text-sm"
                style={{ color: theme.colors.gray }}
              >
                {description}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Options Container */}
      <div className="space-y-3">
        {options.map((option) => {
          const isSelected = isOptionSelected(option.id)

          return (
            <div key={option.id}>
              {/* Option Button */}
              <button
                onClick={() => handleOptionClick(option.id)}
                className="w-full text-left px-4 py-3 rounded-lg border transition-all duration-200"
                style={{
                  backgroundColor: isSelected ? `${theme.colors.secondary}15` : theme.colors.lightBg,
                  borderColor: isSelected ? theme.colors.secondary : theme.colors.border,
                }}
              >
                <div className="flex items-start gap-3">
                  {/* Radio/Checkbox */}
                  <div className="mt-1 shrink-0">
                    {isSelected ? (
                      <CheckCircle size={20} style={{ color: theme.colors.secondary }} />
                    ) : (
                      <Circle size={20} style={{ color: theme.colors.border }} />
                    )}
                  </div>

                  {/* Option Content */}
                  <div className="flex-1 min-w-0">
                    <p
                      className="font-semibold mb-1"
                      style={{ color: theme.colors.primary }}
                    >
                      {option.label}
                    </p>
                    <p
                      className="text-sm mb-2"
                      style={{ color: theme.colors.gray }}
                    >
                      {option.description}
                    </p>

                    {/* Sources Badge */}
                    {option.sources && option.sources.length > 0 && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setExpandedSource(
                            expandedSource === option.id ? null : option.id
                          )
                        }}
                        className="flex items-center gap-1 text-xs font-medium rounded px-2 py-1 transition-colors hover:opacity-80"
                        style={{
                          backgroundColor: `${theme.colors.info}20`,
                          color: theme.colors.info,
                        }}
                      >
                        <BookOpen size={12} />
                        <span>{option.sources.length} reference{option.sources.length !== 1 ? 's' : ''}</span>
                        <ChevronDown
                          size={12}
                          className={`transition-transform ${
                            expandedSource === option.id ? 'rotate-180' : ''
                          }`}
                        />
                      </button>
                    )}
                  </div>
                </div>
              </button>

              {/* Expanded Sources */}
              {expandedSource === option.id && option.sources && (
                <div
                  className="mt-2 p-3 rounded-lg border"
                  style={{
                    backgroundColor: `${theme.colors.info}08`,
                    borderColor: `${theme.colors.info}30`,
                  }}
                >
                  <p
                    className="text-xs font-semibold mb-2"
                    style={{ color: theme.colors.info }}
                  >
                    Regulatory References:
                  </p>
                  <ul className="space-y-1">
                    {option.sources.map((source, idx) => (
                      <li
                        key={idx}
                        className="text-xs"
                        style={{ color: theme.colors.gray }}
                      >
                        <span className="font-mono">→</span> {source}
                      </li>
                    ))}
                  </ul>
                  {option.details && (
                    <p
                      className="text-xs mt-3 pt-3 border-t"
                      style={{
                        borderTopColor: `${theme.colors.info}30`,
                        color: theme.colors.gray,
                      }}
                    >
                      <span className="font-semibold block mb-1">Why this matters:</span>
                      {option.details}
                    </p>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Info Text */}
      <p
        className="text-xs mt-4 pt-4 border-t"
        style={{
          borderTopColor: theme.colors.border,
          color: theme.colors.gray,
        }}
      >
        {multiSelect ? '✓ Select one or more options' : '✓ Select one option to continue'}
      </p>
    </div>
  )
}
