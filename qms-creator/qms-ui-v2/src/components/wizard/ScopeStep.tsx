import { Input } from '../ui/Input'
import { useWizardStore } from '../../stores/useWizardStore'

export function ScopeStep() {
  const { answers, setAnswer } = useWizardStore()

  const questions = [
    { id: 'scope_description', label: 'Describe the scope of this SOP', placeholder: 'What activities, processes, or areas does this SOP cover?' },
    { id: 'scope_exclusions', label: 'Exclusions (if any)', placeholder: 'What is explicitly out of scope?' },
    { id: 'applicable_regulations', label: 'Applicable Regulations', placeholder: 'e.g. EU GMP Annex 7, EudraLex Vol 4, ICH Q10' },
    { id: 'regulatory_bodies', label: 'Regulatory Bodies', placeholder: 'e.g. EMA, national competent authority' },
    { id: 'compliance_standards', label: 'Compliance Standards', placeholder: 'e.g. ISO 9001, GACP, GDP' },
  ]

  return (
    <div className="space-y-5 max-w-xl">
      <p className="text-sm text-slate-400">Define the scope and regulatory context for this SOP.</p>
      {questions.map((q) => (
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
