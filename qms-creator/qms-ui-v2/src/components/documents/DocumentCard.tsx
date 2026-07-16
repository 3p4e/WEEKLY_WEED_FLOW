import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import type { QMSDocument } from '../../types/document'
import { FileText, MoreVertical } from 'lucide-react'

interface DocumentCardProps {
  document: QMSDocument
  onClick: () => void
}

export function DocumentCard({ document, onClick }: DocumentCardProps) {
  const statusVariant = document.status === 'approved' ? 'success' : document.status === 'draft' ? 'warning' : 'info'

  return (
    <Card hover onClick={onClick} className="!p-4">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-emerald-600/10 shrink-0">
          <FileText size={20} className="text-emerald-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between">
            <p className="text-sm font-medium text-slate-200 truncate">{document.title}</p>
            <button
              className="p-1 -mr-1 rounded-md text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-all"
              title="Document actions"
              onClick={(e) => {
                e.stopPropagation();
                // Menu logic here
              }}
            >
              <MoreVertical size={16} />
            </button>
          </div>
          <p className="text-xs text-slate-500 font-mono mt-0.5">{document.code}</p>
          <div className="flex items-center gap-2 mt-2">
            <Badge variant={statusVariant}>{document.status}</Badge>
            <span className="text-xs text-slate-500">{document.department}</span>
          </div>
        </div>
      </div>
    </Card>
  )
}
