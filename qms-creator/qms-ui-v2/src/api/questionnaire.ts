import api from './client'
import type { QuestionnaireSchema, AutofillResponse, CodeSuggestion } from '../types/questionnaire'

export async function initializeQuestionnaire(documentType?: string): Promise<QuestionnaireSchema> {
  const { data } = await api.post('/initialize-questionnaire', { document_type: documentType })
  return data
}

export async function suggestDocumentCode(
  department: string,
  documentType: string
): Promise<CodeSuggestion> {
  const { data } = await api.post('/api/suggest-document-code', { department, document_type: documentType })
  return data
}

export async function autofillQuestions(
  sopName: string,
  department: string,
  questionIds: string[]
): Promise<AutofillResponse> {
  const { data } = await api.post('/api/autofill-questions', {
    sop_name: sopName,
    department,
    question_ids: questionIds,
  })
  return data
}
