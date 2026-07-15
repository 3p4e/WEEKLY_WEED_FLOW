import { AgentCard } from './AgentCard'
import { useGenerationStore } from '../../stores/useGenerationStore'

export function AgentPipeline() {
  const agents = useGenerationStore((s) => s.agents)

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-slate-300 mb-3">Agent Pipeline</h3>
      {agents.map((agent) => (
        <AgentCard key={agent.role} agent={agent} />
      ))}
    </div>
  )
}
