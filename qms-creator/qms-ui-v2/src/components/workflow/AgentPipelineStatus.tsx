import { CheckCircle, Loader2, Circle, AlertCircle } from 'lucide-react'
import { useCurrentTheme } from '../../context/ThemeContext'

export type AgentStatus = 'completed' | 'active' | 'pending' | 'error'

export interface Agent {
  id: string
  name: string
  description?: string
  status: AgentStatus
  duration?: number // in seconds
  errorMessage?: string
  progress?: number // 0-100 for active agents
}

export interface AgentPipelineStatusProps {
  agents: Agent[]
  compact?: boolean
  estimatedTimeRemaining?: number // in seconds
  showDescriptions?: boolean
}

/**
 * AgentPipelineStatus Component
 * Visualizes the 9-agent workflow with real-time status updates
 * Shows which agent is currently active, what's completed, and what's pending
 */
export function AgentPipelineStatus({
  agents,
  compact = false,
  estimatedTimeRemaining,
  showDescriptions = true,
}: AgentPipelineStatusProps) {
  const theme = useCurrentTheme()

  const getStatusIcon = (status: AgentStatus) => {
    switch (status) {
      case 'completed':
        return <CheckCircle size={20} style={{ color: theme.colors.success }} />
      case 'active':
        return <Loader2 size={20} style={{ color: theme.colors.primary }} className="animate-spin" />
      case 'error':
        return <AlertCircle size={20} style={{ color: theme.colors.error }} />
      case 'pending':
      default:
        return <Circle size={20} style={{ color: theme.colors.border }} />
    }
  }

  const getStatusColor = (status: AgentStatus) => {
    switch (status) {
      case 'completed':
        return theme.colors.success
      case 'active':
        return theme.colors.primary
      case 'error':
        return theme.colors.error
      case 'pending':
      default:
        return theme.colors.border
    }
  }

  const formatTime = (seconds?: number) => {
    if (!seconds) return ''
    if (seconds < 60) return `${Math.round(seconds)}s`
    const minutes = Math.floor(seconds / 60)
    const secs = Math.round(seconds % 60)
    return `${minutes}m ${secs}s`
  }

  if (compact) {
    // Compact horizontal layout
    return (
      <div className="flex items-center gap-2 flex-wrap">
        {agents.map((agent, idx) => (
          <div key={agent.id} className="flex items-center gap-1">
            {idx > 0 && (
              <div
                className="w-4 h-0.5"
                style={{ backgroundColor: theme.colors.border }}
              />
            )}
            <div
              className="flex items-center gap-1 px-2 py-1 rounded"
              style={{
                backgroundColor: `${getStatusColor(agent.status)}15`,
              }}
            >
              {getStatusIcon(agent.status)}
              <span className="text-xs font-medium" style={{ color: theme.colors.gray }}>
                {agent.name}
              </span>
            </div>
          </div>
        ))}
      </div>
    )
  }

  // Full vertical layout
  return (
    <div
      className="rounded-lg border p-6"
      style={{
        backgroundColor: theme.colors.lightBg,
        borderColor: theme.colors.border,
      }}
    >
      <h3
        className="text-lg font-semibold mb-4"
        style={{ color: theme.colors.primary }}
      >
        Agent Pipeline Progress
      </h3>

      <div className="space-y-3">
        {agents.map((agent) => (
          <div key={agent.id} className="flex items-start gap-4">
            {/* Status Icon */}
            <div className="mt-1 shrink-0">{getStatusIcon(agent.status)}</div>

            {/* Agent Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                <h4
                  className="font-semibold"
                  style={{ color: theme.colors.primary }}
                >
                  {agent.name}
                </h4>
                {agent.duration && agent.status === 'completed' && (
                  <span className="text-xs" style={{ color: theme.colors.gray }}>
                    {formatTime(agent.duration)}
                  </span>
                )}
              </div>

              {showDescriptions && agent.description && (
                <p
                  className="text-sm mb-2"
                  style={{ color: theme.colors.gray }}
                >
                  {agent.description}
                </p>
              )}

              {/* Progress Bar for Active Agents */}
              {agent.status === 'active' && agent.progress !== undefined && (
                <div
                  className="w-full h-2 rounded-full overflow-hidden"
                  style={{ backgroundColor: theme.colors.border }}
                >
                  <div
                    className="h-full transition-all duration-300"
                    style={{
                      width: `${agent.progress}%`,
                      backgroundColor: theme.colors.primary,
                    }}
                  />
                </div>
              )}

              {/* Error Message */}
              {agent.status === 'error' && agent.errorMessage && (
                <p
                  className="text-sm mt-2 p-2 rounded"
                  style={{
                    backgroundColor: `${theme.colors.error}15`,
                    color: theme.colors.error,
                  }}
                >
                  {agent.errorMessage}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Estimated Time Remaining */}
      {estimatedTimeRemaining && (
        <div
          className="mt-4 pt-4 border-t text-sm"
          style={{
            borderTopColor: theme.colors.border,
            color: theme.colors.gray,
          }}
        >
          <span className="font-medium">Estimated Time Remaining:</span>{' '}
          <span className="font-semibold" style={{ color: theme.colors.primary }}>
            {formatTime(estimatedTimeRemaining)}
          </span>
        </div>
      )}
    </div>
  )
}
