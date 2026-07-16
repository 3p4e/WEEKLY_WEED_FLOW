import { useState } from 'react'
import { Input } from '../ui/Input'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { useWizardStore } from '../../stores/useWizardStore'
import { Plus, Trash2 } from 'lucide-react'

export function OutputStep() {
  const { annexes, addAnnex, removeAnnex } = useWizardStore()
  const [title, setTitle] = useState('')
  const [desc, setDesc] = useState('')

  const handleAdd = () => {
    if (!title.trim()) return
    addAnnex({ id: `annex-${Date.now()}`, title: title.trim(), description: desc.trim() })
    setTitle('')
    setDesc('')
  }

  return (
    <div className="space-y-5 max-w-xl">
      <p className="text-sm text-slate-400">Configure annexes and output preferences.</p>

      {/* Annex list */}
      {annexes.length > 0 && (
        <div className="space-y-2">
          {annexes.map((a, i) => (
            <Card key={a.id} className="flex items-center justify-between py-3 px-4">
              <div>
                <span className="text-xs text-slate-500 font-mono">Annex {String.fromCharCode(65 + i)}</span>
                <p className="text-sm font-medium text-slate-200">{a.title}</p>
                {a.description && <p className="text-xs text-slate-400">{a.description}</p>}
              </div>
              <button onClick={() => removeAnnex(a.id)} className="text-slate-500 hover:text-red-400 p-1">
                <Trash2 size={14} />
              </button>
            </Card>
          ))}
        </div>
      )}

      {/* Add annex */}
      <div className="flex gap-2 items-end">
        <div className="flex-1 space-y-2">
          <Input label="Annex Title" placeholder="e.g. Document Control Form" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Input placeholder="Description (optional)" value={desc} onChange={(e) => setDesc(e.target.value)} />
        </div>
        <Button variant="secondary" size="sm" onClick={handleAdd} icon={<Plus size={14} />}>
          Add
        </Button>
      </div>
    </div>
  )
}
