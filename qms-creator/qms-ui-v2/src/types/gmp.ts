/**
 * EU GMP / Annex 11 Compliance Types and Constants
 *
 * Terminology aligned with:
 * - EU GMP Part I & II
 * - EU GMP Annex 11 (Computerised Systems)
 * - ICH Q9 (Quality Risk Management)
 * - PIC/S Guidance
 */

// ============================================================================
// GMP AUDIT FINDING SEVERITY (per EU GMP inspection terminology)
// ============================================================================

/**
 * GMP Audit Finding Classifications
 * Per EU GMP inspection guidance and PIC/S PI 011-3
 */
export type GMPFindingSeverity = 'critical' | 'major' | 'minor' | 'observation'

export interface GMPFindingConfig {
  severity: GMPFindingSeverity
  label: string
  shortLabel: string
  description: string
  color: string
  bgColor: string
  borderColor: string
  actionRequired: string
}

export const GMP_FINDING_SEVERITY: Record<GMPFindingSeverity, GMPFindingConfig> = {
  critical: {
    severity: 'critical',
    label: 'Critical Deficiency',
    shortLabel: 'Critical',
    description: 'Produced or could produce a product harmful to the patient, or systematic data integrity failure',
    color: 'text-red-400',
    bgColor: 'bg-red-900/20',
    borderColor: 'border-red-600',
    actionRequired: 'Immediate corrective action required before batch release',
  },
  major: {
    severity: 'major',
    label: 'Major Deficiency',
    shortLabel: 'Major',
    description: 'Could result in production of non-compliant product, or significant GMP deviation',
    color: 'text-orange-400',
    bgColor: 'bg-orange-900/20',
    borderColor: 'border-orange-600',
    actionRequired: 'CAPA required within 30 days',
  },
  minor: {
    severity: 'minor',
    label: 'Minor Deficiency',
    shortLabel: 'Minor',
    description: 'Would not be expected to adversely affect product quality',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-900/20',
    borderColor: 'border-yellow-600',
    actionRequired: 'Corrective action recommended',
  },
  observation: {
    severity: 'observation',
    label: 'Observation',
    shortLabel: 'Obs',
    description: 'Improvement opportunity or deviation from best practice',
    color: 'text-blue-400',
    bgColor: 'bg-blue-900/20',
    borderColor: 'border-blue-600',
    actionRequired: 'For consideration in continuous improvement',
  },
}

// Map from internal severity to GMP terminology
export function mapToGMPSeverity(internalSeverity: string): GMPFindingSeverity {
  switch (internalSeverity) {
    case 'critical':
      return 'critical'
    case 'high':
      return 'major'
    case 'medium':
      return 'minor'
    case 'low':
    default:
      return 'observation'
  }
}

// ============================================================================
// SOP GMP RISK CLASSIFICATION (per ICH Q9 / EU GMP risk-based approach)
// ============================================================================

/**
 * SOP GMP Risk Classification
 * Based on ICH Q9 Quality Risk Management principles
 */
export type SOPRiskClassification = 'gmp_critical' | 'gmp_relevant' | 'administrative'

export interface SOPRiskConfig {
  classification: SOPRiskClassification
  label: string
  shortLabel: string
  description: string
  color: string
  bgColor: string
  borderColor: string
  icon: string // Lucide icon name
  auditFrequency: string
  changeControlLevel: string
}

export const SOP_RISK_CLASSIFICATION: Record<SOPRiskClassification, SOPRiskConfig> = {
  gmp_critical: {
    classification: 'gmp_critical',
    label: 'GMP Critical',
    shortLabel: 'Critical',
    description: 'Directly impacts product quality, patient safety, or data integrity',
    color: 'text-red-400',
    bgColor: 'bg-red-900/20',
    borderColor: 'border-red-500',
    icon: 'ShieldAlert',
    auditFrequency: 'Annual review mandatory',
    changeControlLevel: 'QA approval + validation required',
  },
  gmp_relevant: {
    classification: 'gmp_relevant',
    label: 'GMP Relevant',
    shortLabel: 'Relevant',
    description: 'Supports GMP compliance but indirect impact on product quality',
    color: 'text-amber-400',
    bgColor: 'bg-amber-900/20',
    borderColor: 'border-amber-500',
    icon: 'Shield',
    auditFrequency: 'Biennial review',
    changeControlLevel: 'QA approval required',
  },
  administrative: {
    classification: 'administrative',
    label: 'Administrative',
    shortLabel: 'Admin',
    description: 'General business procedures without direct GMP impact',
    color: 'text-slate-400',
    bgColor: 'bg-slate-800/50',
    borderColor: 'border-slate-600',
    icon: 'FileText',
    auditFrequency: 'As needed',
    changeControlLevel: 'Department approval',
  },
}

// SOP category to risk classification mapping
export const SOP_CATEGORY_RISK_MAP: Record<string, SOPRiskClassification> = {
  // GMP Critical - Direct product/patient impact
  'Production': 'gmp_critical',
  'QC_Sampling': 'gmp_critical',
  'QC_Testing': 'gmp_critical',
  'Batch_Release': 'gmp_critical',
  'Sterility': 'gmp_critical',
  'Validation': 'gmp_critical',
  'Deviation_CAPA': 'gmp_critical',
  'Product_Recall': 'gmp_critical',
  'Complaint_Management': 'gmp_critical',
  'Stability': 'gmp_critical',
  'Raw_Materials': 'gmp_critical',
  'Packaging': 'gmp_critical',

  // GMP Relevant - Supporting GMP activities
  'Equipment': 'gmp_relevant',
  'Calibration': 'gmp_relevant',
  'Maintenance': 'gmp_relevant',
  'Sanitation': 'gmp_relevant',
  'Documentation': 'gmp_relevant',
  'Training': 'gmp_relevant',
  'Environmental_Monitoring': 'gmp_relevant',
  'Warehouse': 'gmp_relevant',
  'Utilities': 'gmp_relevant',
  'Pest_Control': 'gmp_relevant',
  'Waste_Management': 'gmp_relevant',
  'Self_Inspection': 'gmp_relevant',

  // Administrative
  'HR': 'administrative',
  'Finance': 'administrative',
  'General': 'administrative',
  'IT_Non_GxP': 'administrative',
}

export function getSOPRiskClassification(category: string): SOPRiskClassification {
  return SOP_CATEGORY_RISK_MAP[category] || 'gmp_relevant'
}

// ============================================================================
// EU GMP ANNEX 11 - DATA INTEGRITY INDICATORS
// ============================================================================

/**
 * ALCOA+ Data Integrity Principles
 * Per EU GMP Annex 11 and MHRA Data Integrity Guidance
 */
export type ALCOAPrinciple =
  | 'attributable'
  | 'legible'
  | 'contemporaneous'
  | 'original'
  | 'accurate'
  | 'complete'
  | 'consistent'
  | 'enduring'
  | 'available'

export interface ALCOAConfig {
  principle: ALCOAPrinciple
  label: string
  description: string
  icon: string
}

export const ALCOA_PRINCIPLES: Record<ALCOAPrinciple, ALCOAConfig> = {
  attributable: {
    principle: 'attributable',
    label: 'Attributable',
    description: 'Who performed action and when',
    icon: 'User',
  },
  legible: {
    principle: 'legible',
    label: 'Legible',
    description: 'Readable and permanent',
    icon: 'Eye',
  },
  contemporaneous: {
    principle: 'contemporaneous',
    label: 'Contemporaneous',
    description: 'Recorded at time of activity',
    icon: 'Clock',
  },
  original: {
    principle: 'original',
    label: 'Original',
    description: 'First capture or certified copy',
    icon: 'FileCheck',
  },
  accurate: {
    principle: 'accurate',
    label: 'Accurate',
    description: 'No errors or editing without documentation',
    icon: 'CheckCircle',
  },
  complete: {
    principle: 'complete',
    label: 'Complete',
    description: 'All data present, including repeat/reanalysis',
    icon: 'ListChecks',
  },
  consistent: {
    principle: 'consistent',
    label: 'Consistent',
    description: 'All elements dated and time-stamped in sequence',
    icon: 'GitBranch',
  },
  enduring: {
    principle: 'enduring',
    label: 'Enduring',
    description: 'Recorded on appropriate media',
    icon: 'HardDrive',
  },
  available: {
    principle: 'available',
    label: 'Available',
    description: 'Accessible for review throughout retention period',
    icon: 'FolderOpen',
  },
}

/**
 * Annex 11 Data Integrity Risk Level
 */
export type DataIntegrityRisk = 'high' | 'medium' | 'low'

export interface DataIntegrityConfig {
  risk: DataIntegrityRisk
  label: string
  description: string
  color: string
  bgColor: string
  gxpRelevance: string
}

export const DATA_INTEGRITY_RISK: Record<DataIntegrityRisk, DataIntegrityConfig> = {
  high: {
    risk: 'high',
    label: 'High DI Risk',
    description: 'Electronic records with batch release impact',
    color: 'text-red-400',
    bgColor: 'bg-red-900/20',
    gxpRelevance: 'GxP Critical - Full Annex 11 compliance required',
  },
  medium: {
    risk: 'medium',
    label: 'Medium DI Risk',
    description: 'Supporting records with traceability requirements',
    color: 'text-amber-400',
    bgColor: 'bg-amber-900/20',
    gxpRelevance: 'GxP Relevant - Key Annex 11 controls required',
  },
  low: {
    risk: 'low',
    label: 'Low DI Risk',
    description: 'Administrative records without GMP impact',
    color: 'text-slate-400',
    bgColor: 'bg-slate-800/50',
    gxpRelevance: 'Non-GxP - Good documentation practice',
  },
}

// ============================================================================
// EU GMP SOURCE AUTHORITY CLASSIFICATION
// ============================================================================

/**
 * Knowledge Base Source Authority
 * Aligned with EU GMP documentation hierarchy
 */
export type GMPSourceAuthority =
  | 'regulatory_binding'      // EudraLex, national laws
  | 'regulatory_guidance'     // ICH, WHO, PIC/S guidance
  | 'industry_standard'       // ISO, ISPE, PDA
  | 'operational_precedent'   // Entity QMS examples

export interface GMPSourceConfig {
  authority: GMPSourceAuthority
  label: string
  shortLabel: string
  description: string
  color: string
  priority: number // Higher = more authoritative
}

export const GMP_SOURCE_AUTHORITY: Record<GMPSourceAuthority, GMPSourceConfig> = {
  regulatory_binding: {
    authority: 'regulatory_binding',
    label: 'Regulatory Requirement',
    shortLabel: 'Regulatory',
    description: 'Legally binding requirement (EudraLex, national law)',
    color: 'text-red-400',
    priority: 10,
  },
  regulatory_guidance: {
    authority: 'regulatory_guidance',
    label: 'Official Guidance',
    shortLabel: 'Guidance',
    description: 'Regulatory guidance document (ICH, WHO, PIC/S)',
    color: 'text-amber-400',
    priority: 8,
  },
  industry_standard: {
    authority: 'industry_standard',
    label: 'Industry Standard',
    shortLabel: 'Standard',
    description: 'Industry standard or best practice (ISO, ISPE, PDA)',
    color: 'text-blue-400',
    priority: 6,
  },
  operational_precedent: {
    authority: 'operational_precedent',
    label: 'Operational Precedent',
    shortLabel: 'Precedent',
    description: 'Entity QMS operational example',
    color: 'text-emerald-400',
    priority: 4,
  },
}

// Map from internal source_authority to GMP terminology
export function mapToGMPSourceAuthority(internal: string): GMPSourceAuthority {
  if (internal === 'official_regulatory') {
    return 'regulatory_guidance'
  }
  return 'operational_precedent'
}

// ============================================================================
// EU GMP CHAPTER REFERENCES
// ============================================================================

export const EU_GMP_CHAPTERS = {
  chapter1: { number: 1, title: 'Pharmaceutical Quality System', annex: null },
  chapter2: { number: 2, title: 'Personnel', annex: null },
  chapter3: { number: 3, title: 'Premises and Equipment', annex: null },
  chapter4: { number: 4, title: 'Documentation', annex: null },
  chapter5: { number: 5, title: 'Production', annex: null },
  chapter6: { number: 6, title: 'Quality Control', annex: null },
  chapter7: { number: 7, title: 'Outsourced Activities', annex: null },
  chapter8: { number: 8, title: 'Complaints and Product Recall', annex: null },
  chapter9: { number: 9, title: 'Self Inspection', annex: null },
  annex11: { number: 11, title: 'Computerised Systems', annex: true },
  annex15: { number: 15, title: 'Qualification and Validation', annex: true },
} as const
