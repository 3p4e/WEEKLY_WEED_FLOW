import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import type { QMSDocument } from '../../types/document'
import { FileText, Clock } from 'lucide-react'

interface RecentActivityProps {
  documents: QMSDocument[]
}

export function RecentActivity({ documents }: RecentActivityProps) {
  const recent = documents.slice(0, 8)

  return (
    <Card className="col-span-full">
      <div className="flex items-center gap-2 mb-4">
        <Clock size={18} className="text-slate-400" />
        <h3 className="text-sm font-semibold text-slate-200">Recent Activity</h3>
      </div>
      {recent.length === 0 ? (
        <p className="text-sm text-slate-500">No documents yet. Create your first SOP.</p>
      ) : (
        <div className="space-y-2">
          {recent.map((doc) => (
            <div
              key={doc.code}
              className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-slate-800/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <FileText size={16} className="text-emerald-400" />
                <div>
                  <p className="text-sm font-medium text-slate-200">{doc.title}</p>
                  <p className="text-xs text-slate-500 font-mono">{doc.code}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Badge variant={doc.status === 'approved' ? 'success' : doc.status === 'draft' ? 'warning' : 'info'}>
                  {doc.status}
                </Badge>
                <span className="text-xs text-slate-500">{doc.department}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
