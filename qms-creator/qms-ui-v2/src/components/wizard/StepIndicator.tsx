import { Check } from 'lucide-react'

const STEPS = ['Metadata', 'Scope', 'Content', 'Output', 'Review']

interface StepIndicatorProps {
  current: number
}

export function StepIndicator({ current }: StepIndicatorProps) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {STEPS.map((label, i) => {
        const done = i < current
        const active = i === current
        return (
          <div key={label} className="flex items-center gap-2">
            <div
              className={`
                w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors
                ${done ? 'bg-emerald-600 text-white' : active ? 'bg-emerald-600/30 text-emerald-400 ring-2 ring-emerald-500' : 'bg-slate-800 text-slate-500'}
              `}
            >
              {done ? <Check size={14} /> : i + 1}
            </div>
            <span className={`text-sm hidden sm:block ${active ? 'text-emerald-400 font-medium' : 'text-slate-500'}`}>
              {label}
            </span>
            {i < STEPS.length - 1 && (
              <div className={`w-8 h-px ${done ? 'bg-emerald-600' : 'bg-slate-700'}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}
