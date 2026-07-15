import { Card } from '../ui/Card'
import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  label: string
  value: string | number
  icon: LucideIcon
  trend?: string
  color?: string
}

export function StatCard({ label, value, icon: Icon, trend, color = 'text-emerald-400' }: StatCardProps) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-400">{label}</p>
          <p className={`text-3xl font-bold mt-1 ${color}`}>{value}</p>
          {trend && <p className="text-xs text-slate-500 mt-1">{trend}</p>}
        </div>
        <div className="p-2.5 rounded-lg bg-slate-800">
          <Icon size={20} className="text-slate-400" />
        </div>
      </div>
    </Card>
  )
}
