import { create } from 'zustand'
import type { Annex } from '../types/questionnaire'

interface WizardState {
  step: number
  // Step 1 — Metadata
  sopName: string
  sopCode: string
  department: string
  facilityType: string
  documentType: string
  // Step 2-3 — Answers
  answers: Record<string, string | string[] | boolean>
  // Step 4 — Annexes
  annexes: Annex[]
  // Actions
  setStep: (step: number) => void
  nextStep: () => void
  prevStep: () => void
  setField: (field: string, value: string) => void
  setAnswer: (id: string, value: string | string[] | boolean) => void
  addAnnex: (annex: Annex) => void
  removeAnnex: (id: string) => void
  reset: () => void
}

const INITIAL = {
  step: 0,
  sopName: '',
  sopCode: '',
  department: '',
  facilityType: '',
  documentType: 'SOP',
  answers: {} as Record<string, string | string[] | boolean>,
  annexes: [] as Annex[],
}

export const useWizardStore = create<WizardState>((set) => ({
  ...INITIAL,
  setStep: (step) => set({ step }),
  nextStep: () => set((s) => ({ step: Math.min(s.step + 1, 4) })),
  prevStep: () => set((s) => ({ step: Math.max(s.step - 1, 0) })),
  setField: (field, value) => set({ [field]: value }),
  setAnswer: (id, value) => set((s) => ({ answers: { ...s.answers, [id]: value } })),
  addAnnex: (annex) => set((s) => ({ annexes: [...s.annexes, annex] })),
  removeAnnex: (id) => set((s) => ({ annexes: s.annexes.filter((a) => a.id !== id) })),
  reset: () => set(INITIAL),
}))
