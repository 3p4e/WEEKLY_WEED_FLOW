import { useState } from 'react'
import { searchKnowledge } from '../../api/rag'
import type { RAGResult, GapInfo } from '../../types/api'
import { SearchResult } from './SearchResult'
import { Button } from '../ui/Button'
import { Skeleton } from '../ui/Skeleton'
import { Search, Database, AlertTriangle, Info, Lightbulb, Shield } from 'lucide-react'
import { GMPSeverityBadge } from '../gmp/GMPBadges'
import { GMP_FINDING_SEVERITY, mapToGMPSeverity } from '../../types/gmp'

type ArchiveFilter = 'both' | 'db1' | 'db2'

export function KnowledgeSearch() {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<ArchiveFilter>('both')
  const [db1Results, setDb1Results] = useState<RAGResult[]>([])
  const [db2Results, setDb2Results] = useState<RAGResult[]>([])
  const [gapInfo, setGapInfo] = useState<GapInfo | null>(null)
  const [dbWeights, setDbWeights] = useState<{ db1: number; db2: number } | null>(null)
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  const handleSearch = async () => {
    if (!query.trim()) return
    setLoading(true)
    setSearched(true)
    setGapInfo(null)
    setDbWeights(null)
    try {
      const results = await searchKnowledge(query, filter === 'both' ? undefined : filter)
      setDb1Results(results.db1_results || [])
      setDb2Results(results.db2_results || [])
      // Store gap info if detected
      if (results.gap_info) {
        setGapInfo(results.gap_info)
      }
      // Store DB weights
      if (results.db_weights) {
        setDbWeights(results.db_weights)
      }
    } catch {
      setDb1Results([])
      setDb2Results([])
    }
    setLoading(false)
  }

  const allResults = [
    ...db1Results.map((r) => ({ ...r, source: 'db1' as const })),
    ...db2Results.map((r) => ({ ...r, source: 'db2' as const })),
  ].sort((a, b) => b.score - a.score)

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Search bar */}
      <div className="space-y-3">
        <div className="relative">
          <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            placeholder="Search regulatory guides and QMS documents..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="w-full pl-11 pr-4 py-3 rounded-xl bg-slate-800/50 border border-slate-700 text-sm text-slate-200 placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-2">
          <Database size={14} className="text-slate-500" />
          {(['both', 'db1', 'db2'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                filter === f ? 'bg-emerald-600/20 text-emerald-400' : 'bg-slate-800 text-slate-500 hover:text-slate-300'
              }`}
            >
              {f === 'both' ? 'Both' : f === 'db1' ? 'Regulatory (DB1)' : 'Entity QMS (DB2)'}
            </button>
          ))}
          <Button variant="primary" size="sm" onClick={handleSearch} loading={loading} className="ml-auto">
            Search
          </Button>
        </div>
      </div>

      {/* GMP Deficiency Warning Banner - EU GMP Terminology */}
      {gapInfo && (() => {
        const gmpSeverity = mapToGMPSeverity(gapInfo.severity)
        const severityConfig = GMP_FINDING_SEVERITY[gmpSeverity]
        return (
          <div className={`rounded-lg border p-4 ${severityConfig.bgColor} ${severityConfig.borderColor}`}>
            <div className="flex items-start gap-3">
              <AlertTriangle size={20} className={`shrink-0 mt-0.5 ${severityConfig.color}`} />
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h4 className={`font-semibold text-sm ${severityConfig.color}`}>
                    GMP {severityConfig.label}: {gapInfo.topic}
                  </h4>
                  <GMPSeverityBadge severity={gapInfo.severity} size="sm" />
                </div>
                <p className="text-xs text-slate-400 mb-2">
                  {gapInfo.description || 'The Entity QMS (DB2) has limited operational precedent for this topic. Results are primarily from official EU GMP regulatory guidance.'}
                </p>
                <div className="flex items-center gap-4 text-xs">
                  {gapInfo.skill_fallback && (
                    <div className="flex items-center gap-1 text-slate-500">
                      <Lightbulb size={12} />
                      <span>
                        CAPA: Use <code className="px-1 py-0.5 rounded bg-black/20">{gapInfo.skill_fallback}</code>
                      </span>
                    </div>
                  )}
                  <div className="flex items-center gap-1 text-slate-600">
                    <Shield size={12} />
                    <span>{severityConfig.actionRequired}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )
      })()}

      {/* Results summary */}
      {searched && !loading && allResults.length > 0 && (
        <div className="flex items-center gap-4 text-xs text-slate-500">
          <div className="flex items-center gap-1">
            <Info size={12} />
            <span>{allResults.length} results</span>
          </div>
          <span>DB1: {db1Results.length}</span>
          <span>DB2: {db2Results.length}</span>
          {dbWeights && (
            <span className="text-slate-600">
              (Weights: DB1={dbWeights.db1}, DB2={dbWeights.db2})
            </span>
          )}
        </div>
      )}

      {/* Results */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
      ) : searched && allResults.length === 0 ? (
        <p className="text-sm text-slate-500 py-8 text-center">No results found.</p>
      ) : (
        <div className="space-y-3">
          {allResults.map((r, i) => (
            <SearchResult key={`${r.source}-${r.id}-${i}`} result={r} source={r.source} />
          ))}
        </div>
      )}
    </div>
  )
}
