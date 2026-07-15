import { AgentPipeline } from './AgentPipeline'
import { LivePreview } from './LivePreview'
import { QualityReport } from './QualityReport'
import { KBContextInfo } from './KBContextInfo'
import { useGenerationStore } from '../../stores/useGenerationStore'
import { Button } from '../ui/Button'
import { ArrowLeft } from 'lucide-react'

interface GenerationViewProps {
  onBack: () => void
}

export function GenerationView({ onBack }: GenerationViewProps) {
  const { isGenerating, error } = useGenerationStore()

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Button variant="ghost" size="sm" onClick={onBack} icon={<ArrowLeft size={16} />}>
          Back to Wizard
        </Button>
        {isGenerating && (
          <span className="text-sm text-emerald-400 animate-pulse">Generating SOP...</span>
        )}
      </div>

      {error && (
        <div className="mb-4 p-4 rounded-lg bg-red-900/20 border border-red-800 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left — Pipeline & KB Context */}
        <div className="lg:col-span-1 space-y-4">
          <AgentPipeline />
          <KBContextInfo />
        </div>
        {/* Right — Preview & Quality */}
        <div className="lg:col-span-2">
          <LivePreview />
          <QualityReport />
        </div>
      </div>
    </div>
  )
}
