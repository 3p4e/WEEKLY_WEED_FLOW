import { motion } from 'framer-motion'
import { Check, SkipForward } from 'lucide-react'
import { useCurrentTheme } from '../../context/ThemeContext'
import type { AgentInfo, AgentNumber, AgentStatus } from '../../types/workflow'

export interface AgentStepperProps {
  agents: AgentInfo[]
  currentAgent: AgentNumber
  onAgentClick?: (agent: AgentNumber) => void
  compact?: boolean
}

/**
 * AgentStepper Component
 * Horizontal 9-step progress stepper showing all agents in the workflow
 * States: pending (gray), in_progress (cyan glow), completed (green), skipped (yellow)
 */
export function AgentStepper({
  agents,
  currentAgent,
  onAgentClick,
  compact = false,
}: AgentStepperProps) {
  const theme = useCurrentTheme()

  const getStatusColors = (status: AgentStatus, isCurrent: boolean) => {
    if (isCurrent && status !== 'completed') {
      return {
        bg: `${theme.colors.primary}20`,
        border: theme.colors.primary,
        text: theme.colors.primary,
        glow: `0 0 20px ${theme.colors.primary}40`,
      }
    }

    switch (status) {
      case 'completed':
        return {
          bg: `${theme.colors.success}20`,
          border: theme.colors.success,
          text: theme.colors.success,
          glow: 'none',
        }
      case 'in_progress':
        return {
          bg: `${theme.colors.primary}20`,
          border: theme.colors.primary,
          text: theme.colors.primary,
          glow: `0 0 20px ${theme.colors.primary}40`,
        }
      case 'skipped':
        return {
          bg: `${theme.colors.warning}20`,
          border: theme.colors.warning,
          text: theme.colors.warning,
          glow: 'none',
        }
      default: // pending
        return {
          bg: 'transparent',
          border: theme.colors.border,
          text: theme.colors.gray,
          glow: 'none',
        }
    }
  }

  const isClickable = (agent: AgentInfo) => {
    return agent.status === 'completed' || agent.number === currentAgent
  }

  return (
    <div className="w-full">
      {/* Header */}
      {!compact && (
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2
              className="text-lg font-semibold"
              style={{ color: theme.colors.primary }}
            >
              9-Agent Workflow
            </h2>
            <p className="text-sm" style={{ color: theme.colors.gray }}>
              Agent {currentAgent} of 9: {agents.find(a => a.number === currentAgent)?.name}
            </p>
          </div>
          <div
            className="px-3 py-1 rounded-lg text-sm font-medium"
            style={{
              backgroundColor: `${theme.colors.secondary}20`,
              color: theme.colors.secondary,
            }}
          >
            {agents.filter(a => a.status === 'completed').length}/9 Completed
          </div>
        </div>
      )}

      {/* Stepper Container */}
      <div className="relative">
        {/* Connection Line */}
        <div
          className="absolute top-6 left-0 right-0 h-0.5"
          style={{
            background: `linear-gradient(to right,
              ${theme.colors.success} ${(agents.filter(a => a.status === 'completed').length / 9) * 100}%,
              ${theme.colors.border} ${(agents.filter(a => a.status === 'completed').length / 9) * 100}%)`,
            zIndex: 0,
          }}
        />

        {/* Agent Steps */}
        <div className="relative flex justify-between items-start">
          {agents.map((agent, index) => {
            const isCurrent = agent.number === currentAgent
            const colors = getStatusColors(agent.status, isCurrent)
            const clickable = isClickable(agent)

            return (
              <div key={agent.number} className="flex flex-col items-center relative z-10">
                {/* Step Circle */}
                <motion.button
                  onClick={() => clickable && onAgentClick?.(agent.number)}
                  disabled={!clickable}
                  className={`
                    relative w-12 h-12 rounded-full flex items-center justify-center
                    border-2 transition-all duration-300
                    ${clickable ? 'cursor-pointer hover:scale-110' : 'cursor-default'}
                  `}
                  style={{
                    backgroundColor: colors.bg,
                    borderColor: colors.border,
                    boxShadow: colors.glow,
                  }}
                  whileHover={clickable ? { scale: 1.1 } : undefined}
                  whileTap={clickable ? { scale: 0.95 } : undefined}
                  animate={isCurrent ? {
                    boxShadow: [
                      `0 0 10px ${theme.colors.primary}40`,
                      `0 0 25px ${theme.colors.primary}60`,
                      `0 0 10px ${theme.colors.primary}40`,
                    ],
                  } : undefined}
                  transition={isCurrent ? {
                    duration: 2,
                    repeat: Infinity,
                    ease: 'easeInOut',
                  } : undefined}
                >
                  {/* Status Icon or Agent Icon */}
                  {agent.status === 'completed' ? (
                    <Check size={20} style={{ color: colors.text }} />
                  ) : agent.status === 'skipped' ? (
                    <SkipForward size={18} style={{ color: colors.text }} />
                  ) : (
                    <span className="text-lg" role="img" aria-label={agent.name}>
                      {agent.icon}
                    </span>
                  )}

                  {/* Current indicator ring */}
                  {isCurrent && agent.status !== 'completed' && (
                    <motion.div
                      className="absolute inset-0 rounded-full border-2"
                      style={{ borderColor: theme.colors.primary }}
                      animate={{ scale: [1, 1.2, 1], opacity: [1, 0.5, 1] }}
                      transition={{ duration: 2, repeat: Infinity }}
                    />
                  )}
                </motion.button>

                {/* Agent Number Badge */}
                <div
                  className="absolute -top-1 -right-1 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold"
                  style={{
                    backgroundColor: colors.border,
                    color: agent.status === 'pending' ? theme.colors.gray : '#fff',
                  }}
                >
                  {agent.number}
                </div>

                {/* Agent Label */}
                {!compact && (
                  <div className="mt-3 text-center max-w-[80px]">
                    <p
                      className="text-xs font-medium leading-tight"
                      style={{
                        color: isCurrent ? theme.colors.primary : colors.text,
                      }}
                    >
                      {agent.name.split(' ')[0]}
                    </p>
                    {isCurrent && (
                      <motion.div
                        className="mt-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
                        style={{
                          backgroundColor: `${theme.colors.primary}30`,
                          color: theme.colors.primary,
                        }}
                        animate={{ opacity: [0.7, 1, 0.7] }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                      >
                        Active
                      </motion.div>
                    )}
                  </div>
                )}

                {/* Connection dot for completed steps */}
                {index < agents.length - 1 && agent.status === 'completed' && (
                  <motion.div
                    className="absolute top-6 -right-4 w-2 h-2 rounded-full"
                    style={{ backgroundColor: theme.colors.success }}
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                  />
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Mobile/Compact Current Agent Info */}
      {compact && (
        <div
          className="mt-4 p-3 rounded-lg flex items-center gap-3"
          style={{
            backgroundColor: `${theme.colors.primary}10`,
            borderLeft: `3px solid ${theme.colors.primary}`,
          }}
        >
          <span className="text-2xl">
            {agents.find(a => a.number === currentAgent)?.icon}
          </span>
          <div>
            <p
              className="text-sm font-semibold"
              style={{ color: theme.colors.primary }}
            >
              Agent {currentAgent}: {agents.find(a => a.number === currentAgent)?.name}
            </p>
            <p className="text-xs" style={{ color: theme.colors.gray }}>
              {agents.find(a => a.number === currentAgent)?.description}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

export default AgentStepper
