import { CheckCircle, Circle } from 'lucide-react'
import { useCurrentTheme } from '../../context/ThemeContext'

export interface WizardStep {
  id: string
  title: string
  description?: string
  completed: boolean
  current: boolean
  optional?: boolean
}

export interface WizardProgressProps {
  steps: WizardStep[]
  currentStep: number
  onStepClick?: (stepIndex: number) => void
}

/**
 * WizardProgress Component
 * Shows the user's progress through the multi-step SOP creation wizard
 * Displays which steps are completed, current, and pending
 */
export function WizardProgress({
  steps,
  currentStep,
  onStepClick,
}: WizardProgressProps) {
  const theme = useCurrentTheme()

  const completedCount = steps.filter((s) => s.completed).length
  const progressPercentage = (completedCount / steps.length) * 100

  return (
    <div className="mb-8">
      {/* Progress Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2
            className="text-lg font-semibold mb-1"
            style={{ color: theme.colors.primary }}
          >
            SOP Creation Progress
          </h2>
          <p className="text-sm" style={{ color: theme.colors.gray }}>
            Step {currentStep + 1} of {steps.length}
          </p>
        </div>
        <div
          className="text-right px-3 py-1 rounded-lg"
          style={{
            backgroundColor: `${theme.colors.secondary}20`,
            color: theme.colors.secondary,
          }}
        >
          <p className="text-sm font-semibold">{Math.round(progressPercentage)}%</p>
          <p className="text-xs">Complete</p>
        </div>
      </div>

      {/* Progress Bar */}
      <div
        className="h-2 rounded-full overflow-hidden mb-6"
        style={{ backgroundColor: theme.colors.border }}
      >
        <div
          className="h-full transition-all duration-500"
          style={{
            width: `${progressPercentage}%`,
            backgroundColor: theme.colors.secondary,
          }}
        />
      </div>

      {/* Steps Timeline */}
      <div className="space-y-2">
        {steps.map((step, index) => {
          const isCompleted = step.completed
          const isCurrent = step.current
          const isPending = !isCompleted && !isCurrent
          const isClickable = isCompleted || isCurrent

          return (
            <button
              key={step.id}
              onClick={() => isClickable && onStepClick?.(index)}
              disabled={!isClickable}
              className={`w-full text-left p-4 rounded-lg border transition-all ${
                isClickable ? 'cursor-pointer hover:shadow-md' : 'cursor-default'
              }`}
              style={{
                backgroundColor: isCurrent ? `${theme.colors.primary}15` : theme.colors.lightBg,
                borderColor: isCurrent ? theme.colors.primary : theme.colors.border,
                opacity: isPending ? 0.6 : 1,
              }}
            >
              <div className="flex items-start gap-4">
                {/* Step Icon */}
                <div className="mt-0.5 shrink-0">
                  {isCompleted ? (
                    <CheckCircle size={24} style={{ color: theme.colors.success }} />
                  ) : isCurrent ? (
                    <div
                      className="w-6 h-6 rounded-full flex items-center justify-center font-bold text-white"
                      style={{ backgroundColor: theme.colors.primary }}
                    >
                      {index + 1}
                    </div>
                  ) : (
                    <Circle size={24} style={{ color: theme.colors.border }} />
                  )}
                </div>

                {/* Step Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3
                      className="font-semibold"
                      style={{
                        color: isCurrent ? theme.colors.primary : theme.colors.gray,
                      }}
                    >
                      {step.title}
                    </h3>
                    {step.optional && (
                      <span
                        className="text-xs px-2 py-0.5 rounded"
                        style={{
                          backgroundColor: `${theme.colors.info}20`,
                          color: theme.colors.info,
                        }}
                      >
                        Optional
                      </span>
                    )}
                  </div>
                  {step.description && (
                    <p
                      className="text-sm"
                      style={{ color: theme.colors.gray }}
                    >
                      {step.description}
                    </p>
                  )}
                </div>

                {/* Step Status */}
                {isCompleted && (
                  <div
                    className="text-xs font-semibold px-2 py-1 rounded whitespace-nowrap mt-0.5"
                    style={{
                      backgroundColor: `${theme.colors.success}20`,
                      color: theme.colors.success,
                    }}
                  >
                    Completed
                  </div>
                )}
                {isCurrent && (
                  <div
                    className="text-xs font-semibold px-2 py-1 rounded whitespace-nowrap mt-0.5 animate-pulse"
                    style={{
                      backgroundColor: `${theme.colors.primary}20`,
                      color: theme.colors.primary,
                    }}
                  >
                    Current
                  </div>
                )}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
