/**
 * EU GMP / Annex 11 Compliant Badge Components
 */
import {
  ShieldAlert,
  Shield,
  FileText,
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle,
  Database,
  Lock,
} from 'lucide-react'
import {
  GMP_FINDING_SEVERITY,
  SOP_RISK_CLASSIFICATION,
  GMP_SOURCE_AUTHORITY,
  DATA_INTEGRITY_RISK,
  mapToGMPSeverity,
  mapToGMPSourceAuthority,
  type SOPRiskClassification,
  type DataIntegrityRisk,
} from '../../types/gmp'

// ============================================================================
// GMP Finding Severity Badge (for gaps/deficiencies)
// ============================================================================

interface GMPSeverityBadgeProps {
  severity: string // Internal severity or GMP severity
  showDescription?: boolean
  size?: 'sm' | 'md'
}

export function GMPSeverityBadge({ severity, showDescription = false, size = 'sm' }: GMPSeverityBadgeProps) {
  const gmpSeverity = mapToGMPSeverity(severity)
  const config = GMP_FINDING_SEVERITY[gmpSeverity]

  const Icon =
    gmpSeverity === 'critical'
      ? AlertTriangle
      : gmpSeverity === 'major'
      ? AlertCircle
      : gmpSeverity === 'minor'
      ? Info
      : CheckCircle

  const sizeClasses = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-3 py-1'

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-medium ${sizeClasses} ${config.bgColor} ${config.color} border ${config.borderColor}`}
      title={showDescription ? undefined : config.description}
    >
      <Icon size={size === 'sm' ? 10 : 12} />
      <span>{config.shortLabel}</span>
      {showDescription && <span className="text-xs opacity-70 ml-1">- {config.description}</span>}
    </span>
  )
}

// ============================================================================
// SOP Risk Classification Badge
// ============================================================================

interface SOPRiskBadgeProps {
  classification: SOPRiskClassification
  showLabel?: boolean
  size?: 'sm' | 'md' | 'lg'
}

export function SOPRiskBadge({ classification, showLabel = true, size = 'md' }: SOPRiskBadgeProps) {
  const config = SOP_RISK_CLASSIFICATION[classification]

  const Icon =
    classification === 'gmp_critical'
      ? ShieldAlert
      : classification === 'gmp_relevant'
      ? Shield
      : FileText

  const sizeConfig = {
    sm: { icon: 10, text: 'text-[10px]', px: 'px-1.5 py-0.5' },
    md: { icon: 12, text: 'text-xs', px: 'px-2 py-1' },
    lg: { icon: 14, text: 'text-sm', px: 'px-3 py-1.5' },
  }

  const s = sizeConfig[size]

  return (
    <span
      className={`inline-flex items-center gap-1 rounded ${s.px} ${s.text} font-medium ${config.bgColor} ${config.color} border ${config.borderColor}`}
      title={config.description}
    >
      <Icon size={s.icon} />
      {showLabel && <span>{config.label}</span>}
    </span>
  )
}

// ============================================================================
// GMP Source Authority Badge (for KB results)
// ============================================================================

interface GMPSourceBadgeProps {
  sourceAuthority: string // Internal or GMP authority
  size?: 'sm' | 'md'
}

export function GMPSourceBadge({ sourceAuthority, size = 'sm' }: GMPSourceBadgeProps) {
  const gmpAuthority = mapToGMPSourceAuthority(sourceAuthority)
  const config = GMP_SOURCE_AUTHORITY[gmpAuthority]

  const Icon =
    gmpAuthority === 'regulatory_binding'
      ? Lock
      : gmpAuthority === 'regulatory_guidance'
      ? Shield
      : gmpAuthority === 'industry_standard'
      ? CheckCircle
      : Database

  const sizeClasses = size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-1'

  return (
    <span
      className={`inline-flex items-center gap-1 rounded ${sizeClasses} font-medium bg-slate-800/50 ${config.color} border border-slate-700`}
      title={config.description}
    >
      <Icon size={size === 'sm' ? 10 : 12} />
      <span>{config.shortLabel}</span>
    </span>
  )
}

// ============================================================================
// Data Integrity Risk Badge (Annex 11)
// ============================================================================

interface DataIntegrityBadgeProps {
  risk: DataIntegrityRisk
  showGxP?: boolean
  size?: 'sm' | 'md'
}

export function DataIntegrityBadge({ risk, showGxP = false, size = 'sm' }: DataIntegrityBadgeProps) {
  const config = DATA_INTEGRITY_RISK[risk]

  const sizeClasses = size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-1'

  return (
    <span
      className={`inline-flex items-center gap-1 rounded ${sizeClasses} font-medium ${config.bgColor} ${config.color} border border-slate-700`}
      title={config.gxpRelevance}
    >
      <Lock size={size === 'sm' ? 10 : 12} />
      <span>{config.label}</span>
      {showGxP && <span className="opacity-70">({config.gxpRelevance.split(' - ')[0]})</span>}
    </span>
  )
}

// ============================================================================
// Composite GMP Indicator (for SOP generation header)
// ============================================================================

interface GMPComplianceIndicatorProps {
  sopCategory?: string
  classification?: SOPRiskClassification
  dataIntegrityRisk?: DataIntegrityRisk
  gapsDetected?: number
}

export function GMPComplianceIndicator({
  sopCategory,
  classification,
  dataIntegrityRisk = 'medium',
  gapsDetected = 0,
}: GMPComplianceIndicatorProps) {
  // Determine classification from category if not provided
  const riskClass = classification || (sopCategory ? getClassificationFromCategory(sopCategory) : 'gmp_relevant')
  const riskConfig = SOP_RISK_CLASSIFICATION[riskClass]

  return (
    <div className={`rounded-lg border p-3 ${riskConfig.bgColor} ${riskConfig.borderColor}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <SOPRiskBadge classification={riskClass} size="md" />
          <span className="text-xs text-slate-400">{riskConfig.auditFrequency}</span>
        </div>
        <div className="flex items-center gap-2">
          <DataIntegrityBadge risk={dataIntegrityRisk} size="sm" />
          {gapsDetected > 0 && (
            <span className="text-[10px] text-yellow-400 flex items-center gap-1">
              <AlertTriangle size={10} />
              {gapsDetected} gap{gapsDetected !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>
      <p className="text-[10px] text-slate-500 mt-2">{riskConfig.changeControlLevel}</p>
    </div>
  )
}

// Helper to get classification from category
function getClassificationFromCategory(category: string): SOPRiskClassification {
  const categoryMap: Record<string, SOPRiskClassification> = {
    Production: 'gmp_critical',
    QC_Sampling: 'gmp_critical',
    QC_Testing: 'gmp_critical',
    Batch_Release: 'gmp_critical',
    Sterility: 'gmp_critical',
    Validation: 'gmp_critical',
    Deviation_CAPA: 'gmp_critical',
    Product_Recall: 'gmp_critical',
    Complaint_Management: 'gmp_critical',
    Equipment: 'gmp_relevant',
    Calibration: 'gmp_relevant',
    Maintenance: 'gmp_relevant',
    Sanitation: 'gmp_relevant',
    Documentation: 'gmp_relevant',
    Training: 'gmp_relevant',
  }
  return categoryMap[category] || 'gmp_relevant'
}

// ============================================================================
// EU GMP Chapter Reference Tag
// ============================================================================

interface GMPChapterTagProps {
  chapter: string // e.g., "Chapter 4", "Annex 11"
  size?: 'sm' | 'md'
}

export function GMPChapterTag({ chapter, size = 'sm' }: GMPChapterTagProps) {
  const isAnnex = chapter.toLowerCase().includes('annex')
  const sizeClasses = size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-1'

  return (
    <span
      className={`inline-flex items-center gap-1 rounded ${sizeClasses} font-mono ${
        isAnnex ? 'bg-purple-900/30 text-purple-300 border-purple-700' : 'bg-blue-900/30 text-blue-300 border-blue-700'
      } border`}
    >
      {chapter}
    </span>
  )
}
