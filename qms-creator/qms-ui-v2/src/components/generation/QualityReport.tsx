import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { useGenerationStore } from '../../stores/useGenerationStore'
import { ShieldCheck, Download } from 'lucide-react'
import { Button } from '../ui/Button'

export function QualityReport() {
  const { qualityReport, docxPath } = useGenerationStore()

  if (!qualityReport && !docxPath) return null

  return (
    <Card className="mt-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ShieldCheck size={18} className="text-emerald-400" />
          <h3 className="text-sm font-semibold text-slate-200">Quality Report</h3>
        </div>
        {docxPath && (
          <a href={docxPath} download>
            <Button variant="secondary" size="sm" icon={<Download size={14} />}>
              Download DOCX
            </Button>
          </a>
        )}
      </div>

      {qualityReport && (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-400">Overall Score:</span>
            <Badge variant={qualityReport.overall_score >= 70 ? 'success' : 'warning'}>
              {qualityReport.overall_score}%
            </Badge>
          </div>

          {qualityReport.compliance_checks.length > 0 && (
            <div className="space-y-1">
              {qualityReport.compliance_checks.map((check, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className={check.passed ? 'text-emerald-400' : 'text-red-400'}>
                    {check.passed ? '✓' : '✗'}
                  </span>
                  <span className="text-slate-400">{check.rule}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
