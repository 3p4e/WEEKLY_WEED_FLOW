/**
 * GMP Compliance Header for SOP Workflow
 * Displays EU GMP risk classification and data integrity requirements
 */
import {
  ShieldAlert,
  Shield,
  FileText,
  Lock,
  Info,
  AlertTriangle,
} from 'lucide-react'
import { useWorkflowStore } from '../../stores/useWorkflowStore'
import { getGMPRiskFromDepartment } from '../../types/workflow'
import {
  SOP_RISK_CLASSIFICATION,
  DATA_INTEGRITY_RISK,
  type SOPRiskClassification,
  type DataIntegrityRisk,
} from '../../types/gmp'

interface GMPComplianceHeaderProps {
  compact?: boolean
  showChangeControl?: boolean
}

export function GMPComplianceHeader({
  compact = false,
  showChangeControl = true,
}: GMPComplianceHeaderProps) {
  const { metadata, qaReview } = useWorkflowStore()

  // Get GMP classification from metadata or derive from department
  const gmpInfo = metadata?.department?.length
    ? getGMPRiskFromDepartment(metadata.department[0])
    : null

  const riskClassification: SOPRiskClassification =
    metadata?.gmpRiskClassification || gmpInfo?.gmpRisk || 'gmp_relevant'
  const dataIntegrityRisk: DataIntegrityRisk =
    metadata?.dataIntegrityRisk || gmpInfo?.dataIntegrityRisk || 'medium'

  const riskConfig = SOP_RISK_CLASSIFICATION[riskClassification]
  const diConfig = DATA_INTEGRITY_RISK[dataIntegrityRisk]

  const RiskIcon =
    riskClassification === 'gmp_critical'
      ? ShieldAlert
      : riskClassification === 'gmp_relevant'
      ? Shield
      : FileText

  // Count gaps/deficiencies from QA review
  const gapCount = qaReview?.gaps?.length || 0

  if (!metadata) return null

  if (compact) {
    return (
      <div
        className={`flex items-center gap-3 px-3 py-2 rounded-lg border ${riskConfig.bgColor} ${riskConfig.borderColor}`}
      >
        <RiskIcon size={16} className={riskConfig.color} />
        <span className={`text-xs font-medium ${riskConfig.color}`}>
          {riskConfig.label}
        </span>
        <span className="text-slate-600">|</span>
        <Lock size={12} className={diConfig.color} />
        <span className={`text-[10px] ${diConfig.color}`}>{diConfig.label}</span>
        {gapCount > 0 && (
          <>
            <span className="text-slate-600">|</span>
            <AlertTriangle size={12} className="text-yellow-400" />
            <span className="text-[10px] text-yellow-400">{gapCount} gaps</span>
          </>
        )}
      </div>
    )
  }

  return (
    <div
      className={`rounded-lg border p-4 ${riskConfig.bgColor} ${riskConfig.borderColor}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <RiskIcon size={20} className={riskConfig.color} />
          <div>
            <h3 className={`text-sm font-semibold ${riskConfig.color}`}>
              EU GMP Classification: {riskConfig.label}
            </h3>
            <p className="text-[10px] text-slate-500">
              {gmpInfo?.euGmpChapter || 'EU GMP Part I'}
            </p>
          </div>
        </div>
        <div
          className={`flex items-center gap-1.5 px-2 py-1 rounded ${diConfig.bgColor}`}
        >
          <Lock size={12} className={diConfig.color} />
          <span className={`text-xs font-medium ${diConfig.color}`}>
            {diConfig.label}
          </span>
        </div>
      </div>

      {/* Description */}
      <p className="text-xs text-slate-400 mb-3">{riskConfig.description}</p>

      {/* Key Requirements Grid */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="flex items-start gap-2">
          <Info size={12} className="text-slate-500 mt-0.5" />
          <div>
            <p className="text-[10px] font-medium text-slate-400">
              Audit Frequency
            </p>
            <p className="text-xs text-slate-300">{riskConfig.auditFrequency}</p>
          </div>
        </div>
        {showChangeControl && (
          <div className="flex items-start gap-2">
            <Shield size={12} className="text-slate-500 mt-0.5" />
            <div>
              <p className="text-[10px] font-medium text-slate-400">
                Change Control
              </p>
              <p className="text-xs text-slate-300">
                {riskConfig.changeControlLevel}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Annex 11 Data Integrity Note */}
      <div className="flex items-start gap-2 pt-2 border-t border-slate-700/50">
        <Lock size={12} className="text-slate-500 mt-0.5" />
        <p className="text-[10px] text-slate-500">
          <span className="font-medium">Annex 11 Requirement:</span>{' '}
          {diConfig.gxpRelevance}
        </p>
      </div>

      {/* Gap Summary if QA review exists */}
      {gapCount > 0 && (
        <div className="flex items-center gap-2 mt-3 pt-2 border-t border-slate-700/50">
          <AlertTriangle size={14} className="text-yellow-400" />
          <span className="text-xs text-yellow-400">
            {gapCount} compliance gap{gapCount !== 1 ? 's' : ''} identified
          </span>
        </div>
      )}
    </div>
  )
}

/**
 * Inline GMP badge for use in headers/toolbars
 */
export function GMPRiskBadgeInline() {
  const { metadata } = useWorkflowStore()

  const gmpInfo = metadata?.department?.length
    ? getGMPRiskFromDepartment(metadata.department[0])
    : null

  const riskClassification: SOPRiskClassification =
    metadata?.gmpRiskClassification || gmpInfo?.gmpRisk || 'gmp_relevant'

  const riskConfig = SOP_RISK_CLASSIFICATION[riskClassification]

  const RiskIcon =
    riskClassification === 'gmp_critical'
      ? ShieldAlert
      : riskClassification === 'gmp_relevant'
      ? Shield
      : FileText

  if (!metadata) return null

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium ${riskConfig.bgColor} ${riskConfig.color} border ${riskConfig.borderColor}`}
      title={riskConfig.description}
    >
      <RiskIcon size={10} />
      {riskConfig.shortLabel}
    </span>
  )
}
