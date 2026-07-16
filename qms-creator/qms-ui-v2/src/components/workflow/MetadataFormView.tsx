import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Plus,
  Trash2,
  Sparkles,
  FileText,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Info,
  Upload,
  X,
  File,
  FileImage,
  Lock,
  Unlock,
} from 'lucide-react'
import { useCurrentTheme } from '../../context/ThemeContext'
import { useWorkflowStore } from '../../stores/useWorkflowStore'
import type { MetadataFormData, AnnexSpecification } from '../../types/workflow'
import { DEPARTMENT_OPTIONS } from '../../types/workflow'
import api from '../../api/client'

interface FormErrors {
  sopTitle?: string
  shortDescription?: string
  department?: string
  annexes?: string
}

interface UploadedFile {
  id: string
  name: string
  size: number
  type: string
  preview?: string
}

/**
 * MetadataFormView Component
 * Agent 1: Collect SOP metadata and specifications
 * Includes AI paraphrase, dynamic annexes, real-time validation
 */
export function MetadataFormView() {
  const theme = useCurrentTheme()
  const { metadata, setMetadata, submitMetadata, isProcessing, error } = useWorkflowStore()

  // Form state
  const [formData, setFormData] = useState<MetadataFormData>(() => {
    if (metadata) {
      // Migration: convert string department to array if needed
      const dept = metadata.department
      const deptArray = Array.isArray(dept) ? dept : (dept ? [dept as unknown as string] : [])
      return {
        ...metadata,
        department: deptArray
      } as MetadataFormData
    }
    return {
      sopTitle: '',
      shortDescription: '',
      department: [],
      documentCode: '',
      annexes: [],
    }
  })

  const [errors, setErrors] = useState<FormErrors>({})

  const [showDraftSaved, setShowDraftSaved] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [isDragging, setIsDragging] = useState(false)

  // Universal enhance state for all text fields
  const [isEnhancing, setIsEnhancing] = useState<Record<string, boolean>>({})
  const [enhancedText, setEnhancedText] = useState<Record<string, string | null>>({})

  // Lock/Check state for context accumulation
  const [lockedFields, setLockedFields] = useState<Record<string, boolean>>({})
  const [accumulatedContext, setAccumulatedContext] = useState<Record<string, string>>({})

  // Generate document code based on department and title
  const generateDocumentCode = useCallback((dept: string | string[], title: string) => {
    if (!dept || (Array.isArray(dept) && dept.length === 0) || !title) return ''
    const primaryDept = Array.isArray(dept) ? dept[0] : dept
    const deptPrefix = primaryDept.toUpperCase().slice(0, 2)
    const titleWords = title.split(' ').slice(0, 3)
    const titleAbbr = titleWords.map(w => w[0]?.toUpperCase() || '').join('')
    const number = String(Math.floor(Math.random() * 99) + 1).padStart(2, '0')
    return `${deptPrefix}_${number}.${titleAbbr}`
  }, [])

  // Validate form
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {}

    if (!formData.sopTitle.trim()) {
      newErrors.sopTitle = 'SOP title is required'
    } else if (formData.sopTitle.length < 10) {
      newErrors.sopTitle = 'Title must be at least 10 characters'
    }

    if (!formData.shortDescription.trim()) {
      newErrors.shortDescription = 'Short description is required'
    } else if (formData.shortDescription.length < 150) {
      newErrors.shortDescription = `Description must be at least 150 characters (${formData.shortDescription.length}/150)`
    }
    // Removed 500-char limit - field can now expand dynamically

    if (formData.department.length === 0) {
      newErrors.department = 'Please select at least one department'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  // Update form field
  const updateField = <K extends keyof MetadataFormData>(
    field: K,
    value: MetadataFormData[K]
  ) => {
    const newData = { ...formData, [field]: value }

    // Auto-generate document code when department or title changes
    if (field === 'department' || field === 'sopTitle') {
      const dept = field === 'department' ? value as string[] : newData.department
      const title = field === 'sopTitle' ? value as string : newData.sopTitle
      newData.documentCode = generateDocumentCode(dept, title)
    }

    setFormData(newData)

    // Clear specific error when field is updated
    if (errors[field as keyof FormErrors]) {
      setErrors(prev => ({ ...prev, [field]: undefined }))
    }
  }

  const toggleDepartment = (deptValue: string) => {
    const currentDepts = formData.department
    let newDepts: string[]
    if (currentDepts.includes(deptValue)) {
      newDepts = currentDepts.filter(d => d !== deptValue)
    } else {
      newDepts = [...currentDepts, deptValue]
    }
    updateField('department', newDepts)
  }



  // Universal enhance text functionality
  const handleEnhanceText = async (fieldName: string, currentValue: string) => {
    if (!currentValue.trim() || currentValue.length < 5) return

    setIsEnhancing(prev => ({ ...prev, [fieldName]: true }))
    try {
      // Build context including accumulated locked fields
      const contextString = getAccumulatedContextString()

      // Call backend API for text enhancement
      const { data } = await api.post('/api/enhance-text', {
        text: currentValue,
        field_type: fieldName,
        context: {
          sop_title: formData.sopTitle,
          department: formData.department,
          uploaded_files: uploadedFiles.map(f => f.name),
          accumulated_context: contextString,
          locked_fields: Object.keys(lockedFields).filter(k => lockedFields[k]),
        },
      })

      setEnhancedText(prev => ({ ...prev, [fieldName]: data.enhanced_text }))
    } catch (err) {
      console.error('Enhancement failed:', err)
      // Fallback to mock enhancement
      const mockEnhanced = `Enhanced: ${currentValue}\n\nThis text has been improved with regulatory context and EU GMP compliance terminology.`
      setEnhancedText(prev => ({ ...prev, [fieldName]: mockEnhanced }))
    } finally {
      setIsEnhancing(prev => ({ ...prev, [fieldName]: false }))
    }
  }

  const applyEnhancedText = (fieldName: string) => {
    const enhanced = enhancedText[fieldName]
    if (!enhanced) return

    // Check if this is an annex field
    if (fieldName.startsWith('annex_')) {
      const parts = fieldName.split('_')
      const annexId = parts[1]
      const field = parts[2] // 'title' or 'desc'

      if (field === 'title') {
        updateAnnex(annexId, 'title', enhanced)
      } else if (field === 'desc') {
        updateAnnex(annexId, 'shortDescription', enhanced)
      }
    } else {
      // Regular field
      updateField(fieldName as keyof MetadataFormData, enhanced as MetadataFormData[keyof MetadataFormData])
    }

    setEnhancedText(prev => ({ ...prev, [fieldName]: null }))
  }

  // Lock/Unlock toggle for context accumulation
  const toggleFieldLock = (fieldName: string, currentValue: string) => {
    const isCurrentlyLocked = lockedFields[fieldName]

    if (isCurrentlyLocked) {
      // Unlock: remove from locked fields and accumulated context
      setLockedFields(prev => ({ ...prev, [fieldName]: false }))
      setAccumulatedContext(prev => {
        const newContext = { ...prev }
        delete newContext[fieldName]
        return newContext
      })
    } else {
      // Lock: add to locked fields and accumulated context
      if (currentValue.trim()) {
        setLockedFields(prev => ({ ...prev, [fieldName]: true }))
        setAccumulatedContext(prev => ({ ...prev, [fieldName]: currentValue }))
      }
    }
  }

  // Get accumulated context for AI operations
  const getAccumulatedContextString = (): string => {
    const contextParts = []
    if (accumulatedContext.sopTitle) {
      contextParts.push(`SOP Title: ${accumulatedContext.sopTitle}`)
    }
    if (accumulatedContext.shortDescription) {
      contextParts.push(`Description: ${accumulatedContext.shortDescription}`)
    }
    if (accumulatedContext.department) {
      contextParts.push(`Department: ${accumulatedContext.department}`)
    }

    // Add any locked annex fields
    Object.keys(accumulatedContext).forEach(key => {
      if (key.startsWith('annex_')) {
        // The key is consistent: annex_<id>_<field>
        if (key.endsWith('_title')) {
          contextParts.push(`Annex Title: ${accumulatedContext[key]}`)
        } else if (key.endsWith('_desc')) {
          contextParts.push(`Annex Description: ${accumulatedContext[key]}`)
        }
      }
    })

    if (uploadedFiles.length > 0) {
      contextParts.push(`Uploaded Files: ${uploadedFiles.map(f => f.name).join(', ')}`)
    }
    return contextParts.join('\n')
  }

  // File upload handlers
  const handleFileUpload = (files: FileList | null) => {
    if (!files) return

    const newFiles: UploadedFile[] = Array.from(files).map(file => ({
      id: `file-${Date.now()}-${Math.random()}`,
      name: file.name,
      size: file.size,
      type: file.type,
    }))

    setUploadedFiles(prev => [...prev, ...newFiles])
  }

  const removeFile = (id: string) => {
    setUploadedFiles(prev => prev.filter(f => f.id !== id))
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    handleFileUpload(e.dataTransfer.files)
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  const getFileIcon = (type: string) => {
    if (type.startsWith('image/')) return <FileImage size={20} />
    return <File size={20} />
  }

  // Annex management
  const addAnnex = () => {
    const newAnnex: AnnexSpecification = {
      id: `annex-${Date.now()}`,
      title: '',
      shortDescription: '',
      intendedPurpose: '',
    }
    updateField('annexes', [...formData.annexes, newAnnex])
  }

  const updateAnnex = (id: string, field: keyof AnnexSpecification, value: string) => {
    const newAnnexes = formData.annexes.map(a =>
      a.id === id ? { ...a, [field]: value } : a
    )
    updateField('annexes', newAnnexes)
  }

  const removeAnnex = (id: string) => {
    updateField('annexes', formData.annexes.filter(a => a.id !== id))
  }

  // Save draft
  const saveDraft = () => {
    setMetadata(formData)
    setShowDraftSaved(true)
    setTimeout(() => setShowDraftSaved(false), 3000)
  }

  // Calculate completion percentage
  const completionPercentage = (() => {
    let completed = 0
    const total = 4 // title, description, department, + bonus for annexes

    if (formData.sopTitle.length >= 10) completed++
    if (formData.shortDescription.length >= 150) completed++
    if (formData.department.length > 0) completed++
    if (formData.annexes.length > 0 && formData.annexes.every(a => a.title && a.shortDescription)) completed++

    return Math.round((completed / total) * 100)
  })()

  // Check if all core fields are locked
  const allCoreFieldsLocked = !!(
    lockedFields.sopTitle &&
    lockedFields.shortDescription &&
    lockedFields.department
  )

  // Submit form
  const handleSubmit = async () => {
    if (!validateForm()) return
    if (!allCoreFieldsLocked) return

    setMetadata(formData)
    await submitMetadata()
  }

  const inputStyle = {
    backgroundColor: `${theme.colors.lightBg}80`,
    borderColor: theme.colors.border,
    color: '#fff',
  }

  const inputFocusStyle = {
    borderColor: theme.colors.primary,
    boxShadow: `0 0 0 2px ${theme.colors.primary}30`,
  }

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
            style={{ backgroundColor: `${theme.colors.primary}20` }}
          >
            📝
          </div>
          <div>
            <h1 className="text-2xl font-bold" style={{ color: theme.colors.primary }}>
              Agent 1: Metadata Orchestrator
            </h1>
            <p style={{ color: theme.colors.gray }}>
              Collect SOP metadata and specifications
            </p>
          </div>
        </div>

        {/* Progress indicator */}
        <div className="mt-4">
          <div className="flex justify-between text-sm mb-1">
            <span style={{ color: theme.colors.gray }}>Form completion</span>
            <span style={{ color: theme.colors.primary }}>{completionPercentage}%</span>
          </div>
          <div
            className="h-2 rounded-full overflow-hidden"
            style={{ backgroundColor: theme.colors.border }}
          >
            <motion.div
              className="h-full"
              style={{ backgroundColor: theme.colors.primary }}
              initial={{ width: 0 }}
              animate={{ width: `${completionPercentage}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 p-4 rounded-lg flex items-start gap-3"
          style={{
            backgroundColor: `${theme.colors.error}20`,
            borderLeft: `3px solid ${theme.colors.error}`,
          }}
        >
          <AlertCircle size={20} style={{ color: theme.colors.error }} />
          <p style={{ color: theme.colors.error }}>{error}</p>
        </motion.div>
      )}

      {/* Form */}
      <div className="space-y-6">
        {/* SOP Title */}
        <div>
          <label className="block text-sm font-medium mb-2" style={{ color: theme.colors.gray }}>
            SOP Title <span style={{ color: theme.colors.error }}>*</span>
          </label>
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <input
                type="text"
                value={formData.sopTitle}
                onChange={(e) => updateField('sopTitle', e.target.value)}
                placeholder="e.g., Document Control and Management"
                className="w-full rounded-lg border px-4 py-3 transition-all outline-none"
                style={{
                  ...inputStyle,
                  borderColor: lockedFields.sopTitle ? theme.colors.success : inputStyle.borderColor,
                  backgroundColor: lockedFields.sopTitle ? `${theme.colors.success}10` : inputStyle.backgroundColor,
                }}
                onFocus={(e) => Object.assign(e.target.style, inputFocusStyle)}
                onBlur={(e) => Object.assign(e.target.style, inputStyle)}
                disabled={lockedFields.sopTitle}
              />
              {formData.sopTitle.length >= 10 && !lockedFields.sopTitle && (
                <CheckCircle2
                  size={18}
                  className="absolute right-3 top-1/2 -translate-y-1/2"
                  style={{ color: theme.colors.success }}
                />
              )}
              {lockedFields.sopTitle && (
                <Lock
                  size={18}
                  className="absolute right-3 top-1/2 -translate-y-1/2"
                  style={{ color: theme.colors.success }}
                />
              )}
            </div>
            <button
              type="button"
              onClick={() => toggleFieldLock('sopTitle', formData.sopTitle)}
              disabled={formData.sopTitle.length < 10}
              className="px-4 py-2 rounded-lg flex items-center gap-2 transition-all disabled:opacity-50"
              style={{
                backgroundColor: lockedFields.sopTitle
                  ? `${theme.colors.success}20`
                  : `${theme.colors.info}20`,
                color: lockedFields.sopTitle ? theme.colors.success : theme.colors.info,
                border: `1px solid ${lockedFields.sopTitle ? theme.colors.success : theme.colors.info}40`,
              }}
              title={lockedFields.sopTitle ? "Unlock to edit" : "Lock to confirm"}
            >
              {lockedFields.sopTitle ? (
                <><Unlock size={18} /><span className="hidden sm:inline">Unlock</span></>
              ) : (
                <><Lock size={18} /><span className="hidden sm:inline">Lock</span></>
              )}
            </button>
            <button
              type="button"
              onClick={() => handleEnhanceText('sopTitle', formData.sopTitle)}
              disabled={isEnhancing.sopTitle || formData.sopTitle.length < 5 || lockedFields.sopTitle}
              className="px-4 py-2 rounded-lg flex items-center gap-2 transition-all disabled:opacity-50"
              style={{
                backgroundColor: `${theme.colors.accent}20`,
                color: theme.colors.accent,
                border: `1px solid ${theme.colors.accent}40`,
              }}
              title="AI Enhance Title"
            >
              {isEnhancing.sopTitle ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Sparkles size={18} />
              )}
              <span className="hidden sm:inline">Enhance</span>
            </button>
          </div>
          {errors.sopTitle && (
            <p className="mt-1 text-sm" style={{ color: theme.colors.error }}>
              {errors.sopTitle}
            </p>
          )}

          {/* Enhanced suggestion */}
          <AnimatePresence>
            {enhancedText.sopTitle && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 p-3 rounded-lg"
                style={{
                  backgroundColor: `${theme.colors.accent}10`,
                  border: `1px solid ${theme.colors.accent}30`,
                }}
              >
                <p className="text-sm mb-2" style={{ color: theme.colors.accent }}>
                  <Sparkles size={14} className="inline mr-1" />
                  AI-enhanced suggestion:
                </p>
                <p className="text-sm mb-3" style={{ color: '#fff' }}>
                  "{enhancedText.sopTitle}"
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => applyEnhancedText('sopTitle')}
                    className="px-3 py-1 text-sm rounded-lg"
                    style={{
                      backgroundColor: theme.colors.accent,
                      color: '#fff',
                    }}
                  >
                    Apply
                  </button>
                  <button
                    onClick={() => setEnhancedText(prev => ({ ...prev, sopTitle: null }))}
                    className="px-3 py-1 text-sm rounded-lg"
                    style={{
                      backgroundColor: 'transparent',
                      color: theme.colors.gray,
                      border: `1px solid ${theme.colors.border}`,
                    }}
                  >
                    Dismiss
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Short Description */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm font-medium" style={{ color: theme.colors.gray }}>
              Short Description <span style={{ color: theme.colors.error }}>*</span>
              <span className="ml-2 text-xs" style={{ color: theme.colors.gray }}>
                (minimum 150 characters)
              </span>
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => toggleFieldLock('shortDescription', formData.shortDescription)}
                disabled={formData.shortDescription.length < 150}
                className="px-3 py-1 rounded-lg flex items-center gap-2 text-sm transition-all disabled:opacity-50"
                style={{
                  backgroundColor: lockedFields.shortDescription
                    ? `${theme.colors.success}20`
                    : `${theme.colors.info}20`,
                  color: lockedFields.shortDescription ? theme.colors.success : theme.colors.info,
                  border: `1px solid ${lockedFields.shortDescription ? theme.colors.success : theme.colors.info}40`,
                }}
                title={lockedFields.shortDescription ? "Unlock to edit" : "Lock to confirm"}
              >
                {lockedFields.shortDescription ? (
                  <><Unlock size={16} /><span>Unlock</span></>
                ) : (
                  <><Lock size={16} /><span>Lock</span></>
                )}
              </button>
              <button
                type="button"
                onClick={() => handleEnhanceText('shortDescription', formData.shortDescription)}
                disabled={isEnhancing.shortDescription || formData.shortDescription.length < 20 || lockedFields.shortDescription}
                className="px-3 py-1 rounded-lg flex items-center gap-2 text-sm transition-all disabled:opacity-50"
                style={{
                  backgroundColor: `${theme.colors.accent}20`,
                  color: theme.colors.accent,
                  border: `1px solid ${theme.colors.accent}40`,
                }}
                title="AI Enhance Description"
              >
                {isEnhancing.shortDescription ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Sparkles size={16} />
                )}
                <span>Enhance</span>
              </button>
            </div>
          </div>
          <div className="relative">
            <textarea
              value={formData.shortDescription}
              onChange={(e) => {
                updateField('shortDescription', e.target.value)
                // Auto-expand textarea
                e.target.style.height = 'auto'
                e.target.style.height = Math.max(e.target.scrollHeight, 100) + 'px'
              }}
              placeholder="Describe the purpose and scope of this SOP... (can be as detailed as needed)"
              rows={4}
              className="w-full rounded-lg border px-4 py-3 transition-all outline-none resize-y min-h-[100px]"
              style={{
                ...inputStyle,
                borderColor: lockedFields.shortDescription ? theme.colors.success : inputStyle.borderColor,
                backgroundColor: lockedFields.shortDescription ? `${theme.colors.success}10` : inputStyle.backgroundColor,
              }}
              onFocus={(e) => Object.assign(e.target.style, inputFocusStyle)}
              onBlur={(e) => Object.assign(e.target.style, inputStyle)}
              disabled={lockedFields.shortDescription}
            />
            <div
              className="absolute bottom-2 right-2 text-xs px-2 py-1 rounded pointer-events-none"
              style={{
                backgroundColor: formData.shortDescription.length >= 150
                  ? `${theme.colors.success}20`
                  : `${theme.colors.warning}20`,
                color: formData.shortDescription.length >= 150
                  ? theme.colors.success
                  : theme.colors.warning,
              }}
            >
              {formData.shortDescription.length} chars
              {formData.shortDescription.length < 150 && ` (need ${150 - formData.shortDescription.length} more)`}
            </div>
          </div>
          {errors.shortDescription && (
            <p className="mt-1 text-sm" style={{ color: theme.colors.error }}>
              {errors.shortDescription}
            </p>
          )}

          {/* Enhanced suggestion for description */}
          <AnimatePresence>
            {enhancedText.shortDescription && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 p-3 rounded-lg"
                style={{
                  backgroundColor: `${theme.colors.accent}10`,
                  border: `1px solid ${theme.colors.accent}30`,
                }}
              >
                <p className="text-sm mb-2" style={{ color: theme.colors.accent }}>
                  <Sparkles size={14} className="inline mr-1" />
                  AI-enhanced suggestion:
                </p>
                <p className="text-sm mb-3 whitespace-pre-wrap" style={{ color: '#fff' }}>
                  {enhancedText.shortDescription}
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => applyEnhancedText('shortDescription')}
                    className="px-3 py-1 text-sm rounded-lg"
                    style={{
                      backgroundColor: theme.colors.accent,
                      color: '#fff',
                    }}
                  >
                    Apply
                  </button>
                  <button
                    onClick={() => setEnhancedText(prev => ({ ...prev, shortDescription: null }))}
                    className="px-3 py-1 text-sm rounded-lg"
                    style={{
                      backgroundColor: 'transparent',
                      color: theme.colors.gray,
                      border: `1px solid ${theme.colors.border}`,
                    }}
                  >
                    Dismiss
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* File Upload Section */}
        <div>
          <label className="block text-sm font-medium mb-2" style={{ color: theme.colors.gray }}>
            Reference Files
            <span className="ml-2 text-xs" style={{ color: theme.colors.gray }}>
              (Optional - upload supporting documents, examples, or images)
            </span>
          </label>

          {/* Drag-and-drop upload zone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className="border-2 border-dashed rounded-lg p-6 text-center transition-all cursor-pointer"
            style={{
              backgroundColor: isDragging ? `${theme.colors.primary}10` : `${theme.colors.lightBg}30`,
              borderColor: isDragging ? theme.colors.primary : theme.colors.border,
            }}
            onClick={() => document.getElementById('file-input')?.click()}
          >
            <Upload
              size={32}
              className="mx-auto mb-2"
              style={{ color: isDragging ? theme.colors.primary : theme.colors.gray }}
            />
            <p className="text-sm mb-1" style={{ color: theme.colors.gray }}>
              {isDragging ? 'Drop files here...' : 'Drag and drop files here, or click to browse'}
            </p>
            <p className="text-xs" style={{ color: theme.colors.gray }}>
              Supports: .txt, .docx, .pdf, .csv, .xlsx, .png, .jpg, .jpeg, .gif, .webp
            </p>
            <input
              id="file-input"
              type="file"
              multiple
              accept=".txt,.docx,.pdf,.csv,.xlsx,.png,.jpg,.jpeg,.gif,.webp"
              onChange={(e) => handleFileUpload(e.target.files)}
              className="hidden"
            />
          </div>

          {/* File preview cards */}
          {uploadedFiles.length > 0 && (
            <div className="mt-3 space-y-2">
              <AnimatePresence mode="popLayout">
                {uploadedFiles.map((file) => (
                  <motion.div
                    key={file.id}
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="flex items-center gap-3 p-3 rounded-lg"
                    style={{
                      backgroundColor: `${theme.colors.lightBg}60`,
                      border: `1px solid ${theme.colors.border}`,
                    }}
                  >
                    <div
                      className="p-2 rounded"
                      style={{ backgroundColor: `${theme.colors.info}20`, color: theme.colors.info }}
                    >
                      {getFileIcon(file.type)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate" style={{ color: '#fff' }}>
                        {file.name}
                      </p>
                      <p className="text-xs" style={{ color: theme.colors.gray }}>
                        {formatFileSize(file.size)}
                      </p>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        removeFile(file.id)
                      }}
                      className="p-2 rounded hover:bg-red-500/20 transition-colors"
                      style={{ color: theme.colors.error }}
                      title="Remove file"
                    >
                      <X size={18} />
                    </button>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>

        {/* Department */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm font-medium" style={{ color: theme.colors.gray }}>
              Department <span style={{ color: theme.colors.error }}>*</span>
            </label>
            <button
              type="button"
              onClick={() => toggleFieldLock('department', formData.department.join(', '))}
              disabled={formData.department.length === 0}
              className="px-3 py-1 rounded-lg flex items-center gap-2 text-sm transition-all disabled:opacity-50"
              style={{
                backgroundColor: lockedFields.department
                  ? `${theme.colors.success}20`
                  : `${theme.colors.info}20`,
                color: lockedFields.department ? theme.colors.success : theme.colors.info,
                border: `1px solid ${lockedFields.department ? theme.colors.success : theme.colors.info}40`,
              }}
              title={lockedFields.department ? "Unlock selection" : "Lock selection"}
            >
              {lockedFields.department ? (
                <><Unlock size={16} /><span>Unlock</span></>
              ) : (
                <><Lock size={16} /><span>Lock</span></>
              )}
            </button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {DEPARTMENT_OPTIONS.map((dept) => (
              <button
                key={dept.value}
                onClick={() => toggleDepartment(dept.value)}
                disabled={lockedFields.department}
                className={`p-3 rounded-lg border transition-all text-center`}
                style={{
                  backgroundColor: formData.department.includes(dept.value)
                    ? `${theme.colors.primary}20`
                    : `${theme.colors.lightBg}50`,
                  borderColor: formData.department.includes(dept.value)
                    ? theme.colors.primary
                    : theme.colors.border,
                  color: formData.department.includes(dept.value)
                    ? theme.colors.primary
                    : theme.colors.gray,
                  opacity: lockedFields.department ? 0.6 : 1,
                  cursor: lockedFields.department ? 'not-allowed' : 'pointer'
                }}
              >
                <span className="text-xl block mb-1">{dept.icon}</span>
                <span className="text-sm font-medium">{dept.label}</span>
              </button>
            ))}
          </div>
          {errors.department && (
            <p className="mt-1 text-sm" style={{ color: theme.colors.error }}>
              {errors.department}
            </p>
          )}
        </div>

        {/* Document Code (Auto-generated) */}
        {formData.documentCode && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <label className="block text-sm font-medium mb-2" style={{ color: theme.colors.gray }}>
              Document Code
              <span
                className="ml-2 text-xs px-2 py-0.5 rounded"
                style={{
                  backgroundColor: `${theme.colors.info}20`,
                  color: theme.colors.info,
                }}
              >
                Auto-generated
              </span>
            </label>
            <div
              className="flex items-center gap-3 p-4 rounded-lg"
              style={{
                backgroundColor: `${theme.colors.secondary}10`,
                border: `1px solid ${theme.colors.secondary}30`,
              }}
            >
              <FileText size={24} style={{ color: theme.colors.secondary }} />
              <span className="font-mono text-lg" style={{ color: '#fff' }}>
                {formData.documentCode}
              </span>
            </div>
          </motion.div>
        )}

        {/* Annexes */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <label className="text-sm font-medium" style={{ color: theme.colors.gray }}>
              Annexes
              <span className="ml-2 text-xs" style={{ color: theme.colors.gray }}>
                (Optional - add forms, templates, flowcharts)
              </span>
            </label>
            <button
              onClick={addAnnex}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm transition-all"
              style={{
                backgroundColor: `${theme.colors.success}20`,
                color: theme.colors.success,
                border: `1px solid ${theme.colors.success}40`,
              }}
            >
              <Plus size={16} />
              Add Annex
            </button>
          </div>

          <AnimatePresence mode="popLayout">
            {formData.annexes.map((annex, index) => (
              <motion.div
                key={annex.id}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mb-4 p-4 rounded-lg"
                style={{
                  backgroundColor: `${theme.colors.lightBg}60`,
                  border: `1px solid ${theme.colors.border}`,
                }}
              >
                <div className="flex items-start justify-between mb-3">
                  <span
                    className="px-2 py-1 rounded text-sm font-semibold"
                    style={{
                      backgroundColor: `${theme.colors.accent}20`,
                      color: theme.colors.accent,
                    }}
                  >
                    Annex {String(index + 1).padStart(2, '0')}
                  </span>
                  <button
                    onClick={() => removeAnnex(annex.id)}
                    className="p-1 rounded hover:bg-red-500/20 transition-colors"
                    style={{ color: theme.colors.error }}
                  >
                    <Trash2 size={18} />
                  </button>
                </div>

                <div className="space-y-3">
                  <div className="flex gap-2">
                    <div className="flex-1 relative">
                      <input
                        type="text"
                        value={annex.title}
                        onChange={(e) => updateAnnex(annex.id, 'title', e.target.value)}
                        placeholder="Annex Title (e.g., Batch Release Checklist)"
                        className="w-full rounded-lg border px-3 py-2 text-sm transition-all outline-none"
                        style={{
                          ...inputStyle,
                          borderColor: lockedFields[`annex_${annex.id}_title`] ? theme.colors.success : inputStyle.borderColor,
                          backgroundColor: lockedFields[`annex_${annex.id}_title`] ? `${theme.colors.success}10` : inputStyle.backgroundColor,
                        }}
                        disabled={lockedFields[`annex_${annex.id}_title`]}
                      />
                      {lockedFields[`annex_${annex.id}_title`] && (
                        <Lock
                          size={14}
                          className="absolute right-3 top-1/2 -translate-y-1/2"
                          style={{ color: theme.colors.success }}
                        />
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => toggleFieldLock(`annex_${annex.id}_title`, annex.title)}
                      disabled={annex.title.length < 5}
                      className="p-2 rounded-lg transition-all disabled:opacity-50"
                      style={{
                        backgroundColor: lockedFields[`annex_${annex.id}_title`] ? `${theme.colors.success}20` : `${theme.colors.info}20`,
                        color: lockedFields[`annex_${annex.id}_title`] ? theme.colors.success : theme.colors.info,
                        border: `1px solid ${lockedFields[`annex_${annex.id}_title`] ? theme.colors.success : theme.colors.info}40`,
                      }}
                      title={lockedFields[`annex_${annex.id}_title`] ? "Unlock" : "Lock"}
                    >
                      {lockedFields[`annex_${annex.id}_title`] ? <Unlock size={18} /> : <Lock size={18} />}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleEnhanceText(`annex_${annex.id}_title`, annex.title)}
                      disabled={isEnhancing[`annex_${annex.id}_title`] || annex.title.length < 5 || lockedFields[`annex_${annex.id}_title`]}
                      className="p-2 rounded-lg flex items-center justify-center transition-all disabled:opacity-50"
                      style={{
                        backgroundColor: `${theme.colors.accent}20`,
                        color: theme.colors.accent,
                        border: `1px solid ${theme.colors.accent}40`,
                      }}
                      title="Enhance annex title"
                    >
                      {isEnhancing[`annex_${annex.id}_title`] ? (
                        <Loader2 size={18} className="animate-spin" />
                      ) : (
                        <Sparkles size={18} />
                      )}
                    </button>
                  </div>

                  <div className="flex gap-2">
                    <div className="flex-1 relative">
                      <textarea
                        value={annex.shortDescription}
                        onChange={(e) => updateAnnex(annex.id, 'shortDescription', e.target.value)}
                        placeholder="Brief description of this annex..."
                        rows={2}
                        className="w-full rounded-lg border px-3 py-2 text-sm transition-all outline-none resize-none"
                        style={{
                          ...inputStyle,
                          borderColor: lockedFields[`annex_${annex.id}_desc`] ? theme.colors.success : inputStyle.borderColor,
                          backgroundColor: lockedFields[`annex_${annex.id}_desc`] ? `${theme.colors.success}10` : inputStyle.backgroundColor,
                        }}
                        disabled={lockedFields[`annex_${annex.id}_desc`]}
                      />
                      {lockedFields[`annex_${annex.id}_desc`] && (
                        <Lock
                          size={14}
                          className="absolute right-3 top-3"
                          style={{ color: theme.colors.success }}
                        />
                      )}
                    </div>
                    <div className="flex flex-col gap-2">
                      <button
                        type="button"
                        onClick={() => toggleFieldLock(`annex_${annex.id}_desc`, annex.shortDescription)}
                        disabled={annex.shortDescription.length < 10}
                        className="p-2 rounded-lg transition-all disabled:opacity-50"
                        style={{
                          backgroundColor: lockedFields[`annex_${annex.id}_desc`] ? `${theme.colors.success}20` : `${theme.colors.info}20`,
                          color: lockedFields[`annex_${annex.id}_desc`] ? theme.colors.success : theme.colors.info,
                          border: `1px solid ${lockedFields[`annex_${annex.id}_desc`] ? theme.colors.success : theme.colors.info}40`,
                        }}
                        title={lockedFields[`annex_${annex.id}_desc`] ? "Unlock" : "Lock"}
                      >
                        {lockedFields[`annex_${annex.id}_desc`] ? <Unlock size={18} /> : <Lock size={18} />}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleEnhanceText(`annex_${annex.id}_desc`, annex.shortDescription)}
                        disabled={isEnhancing[`annex_${annex.id}_desc`] || annex.shortDescription.length < 10 || lockedFields[`annex_${annex.id}_desc`]}
                        className="p-2 rounded-lg flex items-center justify-center transition-all disabled:opacity-50"
                        style={{
                          backgroundColor: `${theme.colors.accent}20`,
                          color: theme.colors.accent,
                          border: `1px solid ${theme.colors.accent}40`,
                        }}
                        title="Enhance annex description"
                      >
                        {isEnhancing[`annex_${annex.id}_desc`] ? (
                          <Loader2 size={18} className="animate-spin" />
                        ) : (
                          <Sparkles size={18} />
                        )}
                      </button>
                    </div>
                  </div>

                  <input
                    type="text"
                    value={annex.intendedPurpose}
                    onChange={(e) => updateAnnex(annex.id, 'intendedPurpose', e.target.value)}
                    placeholder="Intended purpose (e.g., Form, Template, Flowchart, Checklist)"
                    className="w-full rounded-lg border px-3 py-2 text-sm transition-all outline-none"
                    style={inputStyle}
                  />

                  {/* Enhanced suggestions for annex fields */}
                  <AnimatePresence>
                    {(enhancedText[`annex_${annex.id}_title`] || enhancedText[`annex_${annex.id}_desc`]) && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="mt-2 p-2 rounded-lg"
                        style={{
                          backgroundColor: `${theme.colors.accent}10`,
                          border: `1px solid ${theme.colors.accent}30`,
                        }}
                      >
                        <p className="text-xs mb-1" style={{ color: theme.colors.accent }}>
                          <Sparkles size={12} className="inline mr-1" />
                          AI-enhanced suggestion:
                        </p>
                        {enhancedText[`annex_${annex.id}_title`] && (
                          <div className="mb-2">
                            <p className="text-xs font-medium mb-1" style={{ color: theme.colors.gray }}>Title:</p>
                            <p className="text-xs mb-2" style={{ color: '#fff' }}>
                              {enhancedText[`annex_${annex.id}_title`]}
                            </p>
                            <div className="flex gap-2">
                              <button
                                type="button"
                                onClick={() => applyEnhancedText(`annex_${annex.id}_title`)}
                                className="px-2 py-0.5 text-xs rounded"
                                style={{
                                  backgroundColor: theme.colors.accent,
                                  color: '#fff',
                                }}
                              >
                                Apply
                              </button>
                              <button
                                type="button"
                                onClick={() => setEnhancedText(prev => ({ ...prev, [`annex_${annex.id}_title`]: null }))}
                                className="px-2 py-0.5 text-xs rounded"
                                style={{
                                  backgroundColor: 'transparent',
                                  color: theme.colors.gray,
                                  border: `1px solid ${theme.colors.border}`,
                                }}
                              >
                                Dismiss
                              </button>
                            </div>
                          </div>
                        )}
                        {enhancedText[`annex_${annex.id}_desc`] && (
                          <div>
                            <p className="text-xs font-medium mb-1" style={{ color: theme.colors.gray }}>Description:</p>
                            <p className="text-xs mb-2 whitespace-pre-wrap" style={{ color: '#fff' }}>
                              {enhancedText[`annex_${annex.id}_desc`]}
                            </p>
                            <div className="flex gap-2">
                              <button
                                type="button"
                                onClick={() => applyEnhancedText(`annex_${annex.id}_desc`)}
                                className="px-2 py-0.5 text-xs rounded"
                                style={{
                                  backgroundColor: theme.colors.accent,
                                  color: '#fff',
                                }}
                              >
                                Apply
                              </button>
                              <button
                                type="button"
                                onClick={() => setEnhancedText(prev => ({ ...prev, [`annex_${annex.id}_desc`]: null }))}
                                className="px-2 py-0.5 text-xs rounded"
                                style={{
                                  backgroundColor: 'transparent',
                                  color: theme.colors.gray,
                                  border: `1px solid ${theme.colors.border}`,
                                }}
                              >
                                Dismiss
                              </button>
                            </div>
                          </div>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {formData.annexes.length === 0 && (
            <div
              className="p-6 rounded-lg text-center"
              style={{
                backgroundColor: `${theme.colors.lightBg}30`,
                border: `2px dashed ${theme.colors.border}`,
              }}
            >
              <Info size={24} className="mx-auto mb-2" style={{ color: theme.colors.gray }} />
              <p className="text-sm" style={{ color: theme.colors.gray }}>
                No annexes added yet. Click "Add Annex" to include forms, templates, or flowcharts.
              </p>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-6 border-t" style={{ borderColor: theme.colors.border }}>
          <button
            onClick={saveDraft}
            className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all"
            style={{
              backgroundColor: 'transparent',
              color: theme.colors.gray,
              border: `1px solid ${theme.colors.border}`,
            }}
          >
            {showDraftSaved ? (
              <>
                <CheckCircle2 size={18} style={{ color: theme.colors.success }} />
                <span style={{ color: theme.colors.success }}>Saved!</span>
              </>
            ) : (
              'Save Draft'
            )}
          </button>

          <div className="flex flex-col items-end gap-2">
            {!allCoreFieldsLocked && !isProcessing && (
              <div
                className="text-sm flex items-center gap-2 px-3 py-1.5 rounded-lg"
                style={{
                  backgroundColor: `${theme.colors.warning}20`,
                  color: theme.colors.warning,
                }}
              >
                <AlertCircle size={16} />
                {completionPercentage < 75
                  ? `Complete required fields before locking (${completionPercentage}% done)`
                  : "Lock all core fields (Title, Description, Department) to continue"}
              </div>
            )}
            <button
              onClick={handleSubmit}
              disabled={isProcessing || !allCoreFieldsLocked}
              className="flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                background: `linear-gradient(135deg, ${theme.colors.primary}, ${theme.colors.secondary})`,
                color: '#fff',
                boxShadow: `0 4px 15px ${theme.colors.primary}40`,
              }}
              title={!allCoreFieldsLocked ? 'Please lock all fields to continue' : ''}
            >
              {isProcessing ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  Continue to Agent 2
                  <span className="ml-1">→</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default MetadataFormView
