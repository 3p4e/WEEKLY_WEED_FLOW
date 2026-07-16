import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { useWizardStore } from '../../stores/useWizardStore'

export function ReviewStep() {
  const store = useWizardStore()

  const filledAnswers = Object.entries(store.answers).filter(([, v]) => v && String(v).trim())

  return (
    <div className="space-y-5 max-w-2xl">
      <p className="text-sm text-slate-400">Review your inputs before generating the SOP.</p>

      {/* Metadata */}
      <Card>
        <h3 className="text-sm font-semibold text-slate-200 mb-3">Document Metadata</h3>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-slate-500">Name:</span>
            <span className="ml-2 text-slate-200">{store.sopName || '—'}</span>
          </div>
          <div>
            <span className="text-slate-500">Code:</span>
            <span className="ml-2 text-slate-200 font-mono">{store.sopCode || '—'}</span>
          </div>
          <div>
            <span className="text-slate-500">Department:</span>
            <span className="ml-2 text-slate-200">{store.department || '—'}</span>
          </div>
          <div>
            <span className="text-slate-500">Facility:</span>
            <span className="ml-2 text-slate-200">{store.facilityType || '—'}</span>
          </div>
          <div>
            <span className="text-slate-500">Type:</span>
            <Badge>{store.documentType}</Badge>
          </div>
        </div>
      </Card>

      {/* Answers */}
      {filledAnswers.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold text-slate-200 mb-3">Provided Answers</h3>
          <div className="space-y-2 text-sm">
            {filledAnswers.map(([key, val]) => (
              <div key={key} className="flex gap-2">
                <span className="text-slate-500 min-w-[140px] shrink-0">{key.replace(/_/g, ' ')}:</span>
                <span className="text-slate-300">{String(val)}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Annexes */}
      {store.annexes.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold text-slate-200 mb-3">Annexes ({store.annexes.length})</h3>
          <ul className="space-y-1 text-sm">
            {store.annexes.map((a, i) => (
              <li key={a.id} className="text-slate-300">
                <span className="text-slate-500 font-mono">Annex {String.fromCharCode(65 + i)}:</span> {a.title}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
