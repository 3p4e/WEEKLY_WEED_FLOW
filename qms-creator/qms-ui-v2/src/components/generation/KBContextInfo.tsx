import { Card } from '../ui/Card'
import { useGenerationStore } from '../../stores/useGenerationStore'
import { Database, AlertTriangle, BookOpen, Lightbulb, Shield } from 'lucide-react'
import { GMPSeverityBadge } from '../gmp/GMPBadges'
import { GMP_FINDING_SEVERITY, mapToGMPSeverity } from '../../types/gmp'

export function KBContextInfo() {
  const { kbContext, agents, isGenerating } = useGenerationStore()

  // Don't show if no KB context
  if (!kbContext && !isGenerating) return null

  // Calculate stats from agents
  const completedAgents = agents.filter((a) => a.status === 'done')
  const agentsWithGaps = agents.filter((a) => a.kbSources?.gapDetected)

  return (
    <Card className="mb-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Database size={16} className="text-emerald-400" />
          <h3 className="text-sm font-semibold text-slate-200">Knowledge Base Context</h3>
        </div>
        <div className="flex items-center gap-1 text-[10px] text-slate-500">
          <Shield size={10} />
          <span>EU GMP Compliant</span>
        </div>
      </div>

      {/* KB Source Summary */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-slate-800/50 rounded-lg p-3 text-center">
          <div className="text-lg font-bold text-blue-400">
            {kbContext?.totalDb1Sources || 0}
          </div>
          <div className="text-xs text-slate-500">DB1 Sources</div>
          <div className="text-[10px] text-slate-600">Regulatory</div>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3 text-center">
          <div className="text-lg font-bold text-emerald-400">
            {kbContext?.totalDb2Sources || 0}
          </div>
          <div className="text-xs text-slate-500">DB2 Sources</div>
          <div className="text-[10px] text-slate-600">Entity QMS</div>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3 text-center">
          <div className="text-lg font-bold text-purple-400">
            {kbContext?.primarySource === 'db1'
              ? 'Regulatory'
              : kbContext?.primarySource === 'db2'
              ? 'Entity QMS'
              : 'Balanced'}
          </div>
          <div className="text-xs text-slate-500">Primary</div>
          <div className="text-[10px] text-slate-600">Source Type</div>
        </div>
      </div>

      {/* Gap Warnings - EU GMP Deficiency Classification */}
      {kbContext?.gapsDetected && kbContext.gapsDetected.length > 0 && (
        <div className="space-y-2 mb-4">
          <div className="flex items-center gap-2 text-xs text-yellow-400">
            <AlertTriangle size={14} />
            <span className="font-medium">
              GMP Deficiencies Identified ({kbContext.gapsDetected.length})
            </span>
          </div>
          <div className="space-y-1">
            {kbContext.gapsDetected.map((gap, i) => {
              const gmpSeverity = mapToGMPSeverity(gap.severity)
              const severityConfig = GMP_FINDING_SEVERITY[gmpSeverity]
              return (
                <div
                  key={i}
                  className={`flex items-center justify-between rounded px-2 py-1.5 ${severityConfig.bgColor} border ${severityConfig.borderColor}`}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">{gap.section}:</span>
                    <span className="text-xs text-slate-300">{gap.topic}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <GMPSeverityBadge severity={gap.severity} size="sm" />
                    {gap.skillFallback && (
                      <span className="text-[10px] text-slate-500">
                        <Lightbulb size={10} className="inline mr-1" />
                        {gap.skillFallback}
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
          <p className="text-[10px] text-slate-600 italic">
            Classification per EU GMP inspection guidance (PIC/S PI 011-3)
          </p>
        </div>
      )}

      {/* Per-Agent KB Info (collapsed by default) */}
      {completedAgents.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-slate-500 hover:text-slate-300 flex items-center gap-1">
            <BookOpen size={12} />
            <span>KB sources per section ({completedAgents.length} sections)</span>
          </summary>
          <div className="mt-2 space-y-1 pl-4">
            {completedAgents.map((agent) => (
              <div key={agent.role} className="flex items-center justify-between text-slate-500">
                <span>{agent.label}</span>
                <div className="flex items-center gap-2">
                  {agent.kbSources ? (
                    <>
                      <span className="text-blue-400">DB1: {agent.kbSources.db1Count}</span>
                      <span className="text-emerald-400">DB2: {agent.kbSources.db2Count}</span>
                      {agent.kbSources.gapDetected && (
                        <AlertTriangle size={10} className="text-yellow-400" />
                      )}
                    </>
                  ) : (
                    <span className="text-slate-600">-</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Agents with gaps indicator */}
      {agentsWithGaps.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-800">
          <p className="text-[10px] text-slate-600">
            {agentsWithGaps.length} section(s) relied primarily on official regulatory guidance due to limited operational examples in DB2.
          </p>
        </div>
      )}
    </Card>
  )
}
