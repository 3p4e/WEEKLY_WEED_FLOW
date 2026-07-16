import { useEffect } from 'react'
import { Input } from '../ui/Input'
import { Select } from '../ui/Select'
import { Button } from '../ui/Button'
import { Sparkles } from 'lucide-react'
import { useWizardStore } from '../../stores/useWizardStore'
import { suggestDocumentCode } from '../../api/questionnaire'

const DEPARTMENTS = [
  { value: 'Quality Assurance', label: 'Quality Assurance' },
  { value: 'Quality Control', label: 'Quality Control' },
  { value: 'Production', label: 'Production' },
  { value: 'Cultivation', label: 'Cultivation' },
  { value: 'Extraction', label: 'Extraction' },
  { value: 'Packaging', label: 'Packaging' },
  { value: 'Warehouse', label: 'Warehouse' },
  { value: 'Engineering', label: 'Engineering' },
  { value: 'IT', label: 'IT' },
  { value: 'HR', label: 'Human Resources' },
]

const FACILITY_TYPES = [
  { value: 'Indoor Cultivation', label: 'Indoor Cultivation' },
  { value: 'Greenhouse', label: 'Greenhouse' },
  { value: 'Extraction Lab', label: 'Extraction Lab' },
  { value: 'Processing', label: 'Processing Facility' },
  { value: 'Packaging', label: 'Packaging Facility' },
  { value: 'Warehouse', label: 'Warehouse/Distribution' },
]

const DOC_TYPES = [
  { value: 'SOP', label: 'Standard Operating Procedure' },
  { value: 'WI', label: 'Work Instruction' },
  { value: 'Policy', label: 'Policy Document' },
  { value: 'Form', label: 'Form/Template' },
]

export function MetadataStep() {
  const store = useWizardStore()

  const handleSuggestCode = async () => {
    if (!store.department || !store.documentType) return
    try {
      const result = await suggestDocumentCode(store.department, store.documentType)
      store.setField('sopCode', result.suggested_code)
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    if (store.department && store.documentType && !store.sopCode) {
      handleSuggestCode()
    }
  }, [store.department, store.documentType])

  return (
    <div className="space-y-5 max-w-xl">
      <Input
        label="SOP Name"
        placeholder="e.g. Document Control Procedure"
        value={store.sopName}
        onChange={(e) => store.setField('sopName', e.target.value)}
      />

      <div className="flex gap-3 items-end">
        <div className="flex-1">
          <Input
            label="Document Code"
            placeholder="e.g. QA_00.02"
            value={store.sopCode}
            onChange={(e) => store.setField('sopCode', e.target.value)}
            className="font-mono"
          />
        </div>
        <Button variant="ghost" size="sm" onClick={handleSuggestCode} icon={<Sparkles size={14} />}>
          Suggest
        </Button>
      </div>

      <Select
        label="Department"
        options={DEPARTMENTS}
        placeholder="Select department..."
        value={store.department}
        onChange={(e) => store.setField('department', e.target.value)}
      />

      <Select
        label="Facility Type"
        options={FACILITY_TYPES}
        placeholder="Select facility..."
        value={store.facilityType}
        onChange={(e) => store.setField('facilityType', e.target.value)}
      />

      <Select
        label="Document Type"
        options={DOC_TYPES}
        value={store.documentType}
        onChange={(e) => store.setField('documentType', e.target.value)}
      />
    </div>
  )
}
