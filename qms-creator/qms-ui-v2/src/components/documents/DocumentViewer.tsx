import type { QMSDocument } from '../../types/document'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Download, X } from 'lucide-react'

interface DocumentViewerProps {
  document: QMSDocument
  onClose: () => void
}

export function DocumentViewer({ document, onClose }: DocumentViewerProps) {
  const statusVariant = document.status === 'approved' ? 'success' : document.status === 'draft' ? 'warning' : 'info'

  return (
    <div className="border-l border-slate-800 h-full p-5 bg-slate-900/30">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-200">{document.title}</h3>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300 p-1">
          <X size={18} />
        </button>
      </div>

      <div className="space-y-3 text-sm">
        <div className="flex gap-2">
          <span className="text-slate-500 w-24">Code:</span>
          <span className="font-mono text-slate-300">{document.code}</span>
        </div>
        <div className="flex gap-2">
          <span className="text-slate-500 w-24">Department:</span>
          <span className="text-slate-300">{document.department}</span>
        </div>
        <div className="flex gap-2">
          <span className="text-slate-500 w-24">Status:</span>
          <Badge variant={statusVariant}>{document.status}</Badge>
        </div>
        <div className="flex gap-2">
          <span className="text-slate-500 w-24">Version:</span>
          <span className="text-slate-300">{document.version}</span>
        </div>
        <div className="flex gap-2">
          <span className="text-slate-500 w-24">Updated:</span>
          <span className="text-slate-300">{document.updated_at}</span>
        </div>
      </div>

      {document.docx_path && (
        <div className="mt-6">
          <a href={document.docx_path} download>
            <Button variant="secondary" icon={<Download size={14} />}>
              Download DOCX
            </Button>
          </a>
        </div>
      )}
    </div>
  )
}
