import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '../ui/Button'
import { StepIndicator } from './StepIndicator'
import { MetadataStep } from './MetadataStep'
import { ScopeStep } from './ScopeStep'
import { ContentStep } from './ContentStep'
import { OutputStep } from './OutputStep'
import { ReviewStep } from './ReviewStep'
import { useWizardStore } from '../../stores/useWizardStore'
import { ArrowLeft, ArrowRight, Zap } from 'lucide-react'

const STEPS = [MetadataStep, ScopeStep, ContentStep, OutputStep, ReviewStep]

interface WizardShellProps {
  onGenerate: () => void
}

export function WizardShell({ onGenerate }: WizardShellProps) {
  const { step, nextStep, prevStep } = useWizardStore()
  const StepComponent = STEPS[step]
  const isLast = step === STEPS.length - 1

  return (
    <div>
      <StepIndicator current={step} />

      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.2 }}
        >
          <StepComponent />
        </motion.div>
      </AnimatePresence>

      <div className="flex justify-between mt-8 pt-6 border-t border-slate-800">
        <Button
          variant="ghost"
          onClick={prevStep}
          disabled={step === 0}
          icon={<ArrowLeft size={16} />}
        >
          Back
        </Button>

        {isLast ? (
          <Button onClick={onGenerate} icon={<Zap size={16} />} size="lg">
            Generate SOP
          </Button>
        ) : (
          <Button onClick={nextStep} icon={<ArrowRight size={16} />}>
            Continue
          </Button>
        )}
      </div>
    </div>
  )
}
