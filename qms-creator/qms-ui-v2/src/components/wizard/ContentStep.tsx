import { useState } from 'react'
import { Input } from '../ui/Input'
import { Button } from '../ui/Button'
import { useWizardStore } from '../../stores/useWizardStore'
import { autofillQuestions } from '../../api/questionnaire'
import { Sparkles } from 'lucide-react'

const QUESTIONS = [
  { id: 'process_steps', label: 'Key Process Steps', placeholder: 'Describe the main procedure steps' },
  { id: 'equipment_required', label: 'Equipment Required', placeholder: 'List equipment, instruments, or tools' },
  { id: 'quality_parameters', label: 'Quality Parameters', placeholder: 'Critical quality attributes, acceptance criteria' },
  { id: 'training_requirements', label: 'Training Requirements', placeholder: 'Required training, competencies, qualifications' },
  { id: 'deviation_handling', label: 'Deviation Handling', placeholder: 'How are deviations from this SOP handled?' },
  { id: 'risk_considerations', label: 'Risk Considerations', placeholder: 'Key risks and mitigations' },
]

export function ContentStep() {
  const { answers, setAnswer, sopName, department } = useWizardStore()
  const [autofilling, setAutofilling] = useState(false)

  const handleAutofill = async () => {
    setAutofilling(true)
    try {
      const result = await autofillQuestions(
        sopName,
        department,
        QUESTIONS.map((q) => q.id)
      )
      Object.entries(result.suggestions).forEach(([id, value]) => {
        if (value && !answers[id]) setAnswer(id, value)
      })
    } catch {
      // ignore
    }
    setAutofilling(false)
  }

  return (
    <div className="space-y-5 max-w-xl">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">Provide content details for your SOP.</p>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleAutofill}
          loading={autofilling}
          icon={<Sparkles size={14} />}
        >
          AI Autofill All
        </Button>
      </div>
      {QUESTIONS.map((q) => (
        <Input
          key={q.id}
          label={q.label}
          placeholder={q.placeholder}
          value={(answers[q.id] as string) || ''}
          onChange={(e) => setAnswer(q.id, e.target.value)}
        />
      ))}
    </div>
  )
}
