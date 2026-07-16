export interface Question {
  id: string
  text: string
  type: 'text' | 'textarea' | 'select' | 'multiselect' | 'boolean' | 'number'
  required: boolean
  options?: string[]
  default?: string
  placeholder?: string
  section: string
  help_text?: string
}

export interface QuestionnaireSchema {
  sections: QuestionnaireSection[]
  metadata: Record<string, unknown>
}

export interface QuestionnaireSection {
  id: string
  title: string
  description: string
  questions: Question[]
}

export interface SOPRequest {
  sop_name: string
  sop_code: string
  department: string
  facility_type: string
  document_type: string
  answers: Record<string, string | string[] | boolean>
  annexes: Annex[]
}

export interface Annex {
  id: string
  title: string
  description: string
}

export interface AutofillResponse {
  suggestions: Record<string, string>
}

export interface CodeSuggestion {
  suggested_code: string
  department_prefix: string
  next_number: string
}
