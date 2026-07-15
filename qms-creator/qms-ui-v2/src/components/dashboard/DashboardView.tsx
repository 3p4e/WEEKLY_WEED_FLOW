import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Building2, ShieldCheck, AlertCircle } from 'lucide-react'
import { StatCard } from './StatCard'
import { RecentActivity } from './RecentActivity'
import { Button } from '../ui/Button'
import { Skeleton } from '../ui/Skeleton'
import { getStats, getDocuments } from '../../api/documents'
import type { StatsResponse } from '../../types/api'
import type { QMSDocument } from '../../types/document'

export function DashboardView() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [documents, setDocuments] = useState<QMSDocument[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getStats(), getDocuments()])
      .then(([s, d]) => {
        setStats(s)
        setDocuments(d)
      })
      .catch(() => {
        // Backend might not be running — show empty state
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
        <Skeleton className="col-span-full h-64" />
      </div>
    )
  }

  const totalDocs = stats?.total_documents ?? 0
  const deptCount = stats ? Object.keys(stats.departments).length : 0
  const approvedCount = stats?.status_counts?.approved ?? 0
  const draftCount = stats?.status_counts?.draft ?? 0

  return (
    <div className="space-y-6">
      {/* CTA */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-100">Quality Management System</h2>
          <p className="text-sm text-slate-400 mt-1">Cannabis EU GMP Compliance</p>
        </div>
        <Button onClick={() => navigate('/create')} size="lg">
          Create New SOP
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total SOPs" value={totalDocs} icon={FileText} />
        <StatCard label="Departments" value={deptCount} icon={Building2} color="text-blue-400" />
        <StatCard label="Approved" value={approvedCount} icon={ShieldCheck} color="text-emerald-400" />
        <StatCard label="Drafts" value={draftCount} icon={AlertCircle} color="text-amber-400" />
      </div>

      {/* Recent */}
      <RecentActivity documents={documents} />
    </div>
  )
}
