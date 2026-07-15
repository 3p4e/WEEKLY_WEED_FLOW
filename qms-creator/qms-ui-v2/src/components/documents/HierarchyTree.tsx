import { useState, useEffect } from 'react'
import { getHierarchy } from '../../api/documents'
import type { HierarchyNode } from '../../types/api'
import { ChevronRight, ChevronDown, FileText, Folder } from 'lucide-react'

export function HierarchyTree() {
  const [tree, setTree] = useState<HierarchyNode[]>([])

  useEffect(() => {
    getHierarchy().then(setTree).catch(() => {})
  }, [])

  if (tree.length === 0) return <p className="text-xs text-slate-500 p-3">No hierarchy data</p>

  return (
    <div className="text-sm space-y-0.5">
      {tree.map((node) => (
        <TreeNode key={node.code} node={node} depth={0} />
      ))}
    </div>
  )
}

function TreeNode({ node, depth }: { node: HierarchyNode; depth: number }) {
  const [open, setOpen] = useState(false)
  const hasChildren = node.children && node.children.length > 0

  return (
    <div>
      <button
        onClick={() => hasChildren && setOpen(!open)}
        className="flex items-center gap-1.5 w-full px-2 py-1.5 rounded hover:bg-slate-800/50 transition-colors"
        style={{ paddingLeft: depth * 16 + 8 }}
      >
        {hasChildren ? (
          open ? <ChevronDown size={14} className="text-slate-500" /> : <ChevronRight size={14} className="text-slate-500" />
        ) : (
          <FileText size={14} className="text-slate-600" />
        )}
        {hasChildren && <Folder size={14} className="text-amber-500/70" />}
        <span className="text-slate-300 truncate">{node.title || node.code}</span>
        <span className="text-xs text-slate-600 font-mono ml-auto">{node.code}</span>
      </button>
      {open && node.children?.map((child) => (
        <TreeNode key={child.code} node={child} depth={depth + 1} />
      ))}
    </div>
  )
}
