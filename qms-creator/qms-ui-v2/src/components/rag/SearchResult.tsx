import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import type { RAGResult } from '../../types/api'
import { useState } from 'react'
import { ChevronDown, ChevronUp, Star, FileText, Lock, Database, CheckCircle } from 'lucide-react'
import { GMP_SOURCE_AUTHORITY, mapToGMPSourceAuthority } from '../../types/gmp'

interface SearchResultProps {
  result: RAGResult
  source: 'db1' | 'db2'
}

// Quality score color based on value - aligned with EU GMP acceptability
function getQualityColor(quality: number): string {
  if (quality >= 8) return 'text-emerald-400' // Acceptable
  if (quality >= 6) return 'text-yellow-400'  // Needs review
  return 'text-orange-400'                     // Requires attention
}

// Quality label per EU GMP expectations
function getQualityLabel(quality: number): string {
  if (quality >= 8) return 'GMP Compliant'
  if (quality >= 6) return 'Review Required'
  return 'Attention Required'
}

// Format category name for display
function formatCategory(category: string): string {
  return category
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .trim()
}

export function SearchResult({ result, source }: SearchResultProps) {
  const [expanded, setExpanded] = useState(false)
  const preview = result.text.slice(0, 200)
  const hasMore = result.text.length > 200

  const fileTags = result.tags.filter((t) => t.startsWith('file:'))
  const bodyTags = result.tags.filter((t) => t.startsWith('regulatory_body:'))

  // Extract metadata if available
  const metadata = result.metadata
  const hasMetadata = !!metadata

  return (
    <Card className="!p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Top row: EU GMP source badge, category, and relevance score */}
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <Badge variant={source === 'db1' ? 'info' : 'success'}>
              {source === 'db1' ? 'EU GMP Regulatory' : 'Operational QMS'}
            </Badge>
            {bodyTags.map((t) => (
              <Badge key={t} variant="default">{t.split(':')[1]}</Badge>
            ))}
            {/* Category badge from metadata */}
            {hasMetadata && metadata.category && metadata.category !== 'General' && (
              <Badge variant="default" className="bg-purple-900/30 text-purple-300 border-purple-700">
                <FileText size={10} className="mr-1" />
                {formatCategory(metadata.category)}
              </Badge>
            )}
            <span className="text-xs text-slate-600 ml-auto">{(result.score * 100).toFixed(0)}%</span>
          </div>

          {/* Metadata row: Quality score and GMP source authority */}
          {hasMetadata && (() => {
            const gmpAuthority = mapToGMPSourceAuthority(metadata.source_authority)
            const authorityConfig = GMP_SOURCE_AUTHORITY[gmpAuthority]
            const AuthorityIcon = gmpAuthority === 'regulatory_binding' || gmpAuthority === 'regulatory_guidance'
              ? Lock
              : gmpAuthority === 'industry_standard'
              ? CheckCircle
              : Database

            return (
              <div className="flex items-center gap-3 mb-2 text-xs flex-wrap">
                {/* Quality score - GMP aligned */}
                <div className={`flex items-center gap-1 ${getQualityColor(metadata.quality)}`}>
                  <Star size={12} />
                  <span>{getQualityLabel(metadata.quality)}</span>
                  <span className="text-slate-600">({metadata.quality}/10)</span>
                </div>
                {/* GMP Source Authority */}
                <div
                  className={`flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-800/50 ${authorityConfig.color}`}
                  title={authorityConfig.description}
                >
                  <AuthorityIcon size={10} />
                  <span className="text-[10px] font-medium">{authorityConfig.shortLabel}</span>
                </div>
                {/* Priority indicator */}
                <span className="text-[10px] text-slate-600">
                  Priority: {authorityConfig.priority}/10
                </span>
              </div>
            )
          })()}

          {/* Content text */}
          <p className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
            {expanded ? result.text : preview}
            {hasMore && !expanded && '...'}
          </p>

          {/* File name */}
          {fileTags.length > 0 && (
            <p className="text-xs text-slate-600 mt-2 font-mono">{fileTags[0].split(':')[1]}</p>
          )}
        </div>
        {hasMore && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-slate-500 hover:text-slate-300 p-1 shrink-0"
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        )}
      </div>
    </Card>
  )
}
