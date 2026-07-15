import { useEffect, useState } from 'react'
import { getDocuments } from '../../api/documents'
import type { QMSDocument } from '../../types/document'
import { DocumentCard } from './DocumentCard'
import { DocumentViewer } from './DocumentViewer'
import { HierarchyTree } from './HierarchyTree'
import { LayoutGrid, List, Search } from 'lucide-react'
import { Skeleton } from '../ui/Skeleton'

export function DocumentLibrary() {
  const [documents, setDocuments] = useState<QMSDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [selected, setSelected] = useState<QMSDocument | null>(null)

  useEffect(() => {
    getDocuments()
      .then(setDocuments)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const filtered = documents.filter(
    (d) =>
      d.title.toLowerCase().includes(search.toLowerCase()) ||
      d.code.toLowerCase().includes(search.toLowerCase()) ||
      d.department.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="flex gap-6 h-[calc(100vh-10rem)]">
      {/* Sidebar — Tree */}
      <div className="w-64 shrink-0 border-r border-slate-800 overflow-y-auto pr-4">
        <h3 className="text-sm font-semibold text-slate-300 mb-3">QMS Hierarchy</h3>
        <HierarchyTree />
      </div>

      {/* Main */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex-1 relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              placeholder="Search documents..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 rounded-lg bg-slate-800/50 border border-slate-700 text-sm text-slate-200 placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <div className="flex border border-slate-700 rounded-lg overflow-hidden">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 ${viewMode === 'grid' ? 'bg-slate-700 text-slate-200' : 'text-slate-500 hover:text-slate-300'}`}
            >
              <LayoutGrid size={16} />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 ${viewMode === 'list' ? 'bg-slate-700 text-slate-200' : 'text-slate-500 hover:text-slate-300'}`}
            >
              <List size={16} />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-24" />)}
          </div>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-slate-500 py-8 text-center">No documents found.</p>
        ) : (
          <div className={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3' : 'space-y-2'}>
            {filtered.map((doc) => (
              <DocumentCard key={doc.code} document={doc} onClick={() => setSelected(doc)} />
            ))}
          </div>
        )}
      </div>

      {/* Detail panel */}
      {selected && (
        <div className="w-80 shrink-0">
          <DocumentViewer document={selected} onClose={() => setSelected(null)} />
        </div>
      )}
    </div>
  )
}
