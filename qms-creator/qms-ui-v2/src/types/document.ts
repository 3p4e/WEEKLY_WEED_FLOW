export interface QMSDocument {
  code: string
  title: string
  department: string
  status: DocumentStatus
  version: string
  created_at: string
  updated_at: string
  docx_path?: string
  pdf_path?: string
  sections?: string[]
}

export type DocumentStatus = 'draft' | 'review' | 'approved' | 'archived' | 'superseded'

export const STATUS_COLORS: Record<DocumentStatus, string> = {
  draft: 'bg-amber-500/20 text-amber-400',
  review: 'bg-blue-500/20 text-blue-400',
  approved: 'bg-emerald-500/20 text-emerald-400',
  archived: 'bg-slate-500/20 text-slate-400',
  superseded: 'bg-red-500/20 text-red-400',
}
