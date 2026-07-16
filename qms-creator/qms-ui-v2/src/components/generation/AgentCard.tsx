import { motion } from 'framer-motion'
import { Check, Loader2, AlertCircle, Clock, AlertTriangle, Database } from 'lucide-react'
import type { AgentState } from '../../types/generation'

interface AgentCardProps {
  agent: AgentState
}

const STATUS_CONFIG = {
  waiting: { icon: Clock, bg: 'bg-slate-800', border: 'border-slate-700', text: 'text-slate-500' },
  working: { icon: Loader2, bg: 'bg-emerald-900/30', border: 'border-emerald-600/50', text: 'text-emerald-400' },
  done: { icon: Check, bg: 'bg-emerald-900/20', border: 'border-emerald-700/30', text: 'text-emerald-400' },
  error: { icon: AlertCircle, bg: 'bg-red-900/20', border: 'border-red-700/30', text: 'text-red-400' },
}

export function AgentCard({ agent }: AgentCardProps) {
  const config = STATUS_CONFIG[agent.status]
  const Icon = config.icon
  const hasKBSources = agent.kbSources && (agent.kbSources.db1Count > 0 || agent.kbSources.db2Count > 0)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className={`
        flex items-center gap-3 px-4 py-3 rounded-lg border transition-all
        ${config.bg} ${config.border}
        ${agent.status === 'working' ? 'animate-agent-pulse' : ''}
      `}
    >
      <div className={`shrink-0 ${config.text}`}>
        <Icon size={18} className={agent.status === 'working' ? 'animate-spin' : ''} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className={`text-sm font-medium ${agent.status === 'waiting' ? 'text-slate-400' : 'text-slate-200'}`}>
            {agent.label}
          </p>
          {/* Gap indicator */}
          {agent.kbSources?.gapDetected && (
            <span title={`Gap: ${agent.kbSources.gapTopic || 'Unknown'}`}>
              <AlertTriangle size={12} className="text-yellow-500" />
            </span>
          )}
        </div>
        {agent.status === 'done' && agent.content && (
          <p className="text-xs text-slate-500 truncate mt-0.5">{agent.content.slice(0, 80)}...</p>
        )}
        {agent.error && <p className="text-xs text-red-400 mt-0.5">{agent.error}</p>}
        {/* KB Sources info */}
        {agent.status === 'done' && hasKBSources && agent.kbSources && (
          <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-600">
            <Database size={10} />
            <span className="text-blue-400/70">DB1: {agent.kbSources.db1Count}</span>
            <span className="text-emerald-400/70">DB2: {agent.kbSources.db2Count}</span>
          </div>
        )}
      </div>
    </motion.div>
  )
}
