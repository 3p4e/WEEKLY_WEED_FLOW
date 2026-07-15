import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  MessageSquare,
  Edit3,
  Flag,
  X,
  Send,
  Sparkles,
} from 'lucide-react'
import { useCurrentTheme } from '../../context/ThemeContext'
import type { TextSelection } from './DocumentPreview'

interface AnnotationToolbarProps {
  selection: TextSelection | null
  onComment: (text: string, comment: string) => void
  onSuggestEdit: (text: string, suggestion: string) => void
  onFlag: (text: string, reason: string) => void
  onClose: () => void
}

type ActionMode = 'none' | 'comment' | 'edit' | 'flag'

/**
 * AnnotationToolbar Component
 * Floating toolbar that appears when text is selected
 * Allows commenting, suggesting edits, and flagging content
 */
export function AnnotationToolbar({
  selection,
  onComment,
  onSuggestEdit,
  onFlag,
  onClose,
}: AnnotationToolbarProps) {
  const theme = useCurrentTheme()
  const toolbarRef = useRef<HTMLDivElement>(null)

  const [actionMode, setActionMode] = useState<ActionMode>('none')
  const [inputValue, setInputValue] = useState('')
  const [position, setPosition] = useState({ top: 0, left: 0 })

  // Calculate toolbar position based on selection
  useEffect(() => {
    if (selection && toolbarRef.current) {
      const { rect } = selection
      const toolbarHeight = toolbarRef.current.offsetHeight

      // Position above the selection
      let top = rect.top - toolbarHeight - 10 + window.scrollY
      let left = rect.left + (rect.width / 2) - 100 // Center the toolbar

      // Ensure toolbar stays within viewport
      if (top < 10) {
        top = rect.bottom + 10 + window.scrollY // Position below if no space above
      }
      if (left < 10) left = 10
      if (left + 200 > window.innerWidth) left = window.innerWidth - 210

      // eslint-disable-next-line react-hooks/set-state-in-effect -- position depends on DOM measurement (offsetHeight), only available after render
      setPosition({ top, left })
    }
  }, [selection])

  // Reset state when selection changes
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional reset when the external selection changes
    setActionMode('none')
    setInputValue('')
  }, [selection])

  const handleSubmit = () => {
    if (!selection || !inputValue.trim()) return

    switch (actionMode) {
      case 'comment':
        onComment(selection.text, inputValue)
        break
      case 'edit':
        onSuggestEdit(selection.text, inputValue)
        break
      case 'flag':
        onFlag(selection.text, inputValue)
        break
    }

    setActionMode('none')
    setInputValue('')
    onClose()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
    if (e.key === 'Escape') {
      if (actionMode !== 'none') {
        setActionMode('none')
        setInputValue('')
      } else {
        onClose()
      }
    }
  }

  if (!selection) return null

  const getActionLabel = () => {
    switch (actionMode) {
      case 'comment':
        return 'Add a comment...'
      case 'edit':
        return 'Suggest an edit...'
      case 'flag':
        return 'Reason for flagging...'
      default:
        return ''
    }
  }

  const getActionColor = () => {
    switch (actionMode) {
      case 'comment':
        return theme.colors.info
      case 'edit':
        return theme.colors.accent
      case 'flag':
        return theme.colors.warning
      default:
        return theme.colors.primary
    }
  }

  return (
    <AnimatePresence>
      <motion.div
        ref={toolbarRef}
        initial={{ opacity: 0, scale: 0.9, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.9, y: 10 }}
        className="fixed z-50"
        style={{
          top: position.top,
          left: position.left,
        }}
      >
        <div
          className="rounded-xl shadow-lg overflow-hidden"
          style={{
            backgroundColor: theme.colors.lightBg,
            border: `1px solid ${theme.colors.border}`,
            boxShadow: `0 8px 32px rgba(0, 0, 0, 0.4), 0 0 20px ${theme.colors.primary}20`,
          }}
        >
          {/* Action Buttons */}
          {actionMode === 'none' && (
            <div className="flex items-center gap-1 p-2">
              <button
                onClick={() => setActionMode('comment')}
                className="flex items-center gap-2 px-3 py-2 rounded-lg transition-all hover:scale-105"
                style={{
                  backgroundColor: `${theme.colors.info}20`,
                  color: theme.colors.info,
                }}
                title="Add comment"
              >
                <MessageSquare size={16} />
                <span className="text-sm">Comment</span>
              </button>

              <button
                onClick={() => setActionMode('edit')}
                className="flex items-center gap-2 px-3 py-2 rounded-lg transition-all hover:scale-105"
                style={{
                  backgroundColor: `${theme.colors.accent}20`,
                  color: theme.colors.accent,
                }}
                title="Suggest edit"
              >
                <Edit3 size={16} />
                <span className="text-sm">Edit</span>
              </button>

              <button
                onClick={() => setActionMode('flag')}
                className="flex items-center gap-2 px-3 py-2 rounded-lg transition-all hover:scale-105"
                style={{
                  backgroundColor: `${theme.colors.warning}20`,
                  color: theme.colors.warning,
                }}
                title="Flag for review"
              >
                <Flag size={16} />
                <span className="text-sm">Flag</span>
              </button>

              <div
                className="w-px h-8 mx-1"
                style={{ backgroundColor: theme.colors.border }}
              />

              <button
                onClick={onClose}
                className="p-2 rounded-lg transition-colors hover:bg-white/10"
                style={{ color: theme.colors.gray }}
                title="Close"
              >
                <X size={16} />
              </button>
            </div>
          )}

          {/* Input Mode */}
          {actionMode !== 'none' && (
            <div className="p-3 min-w-[300px]">
              {/* Header */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {actionMode === 'comment' && <MessageSquare size={16} style={{ color: getActionColor() }} />}
                  {actionMode === 'edit' && <Edit3 size={16} style={{ color: getActionColor() }} />}
                  {actionMode === 'flag' && <Flag size={16} style={{ color: getActionColor() }} />}
                  <span
                    className="text-sm font-medium"
                    style={{ color: getActionColor() }}
                  >
                    {actionMode === 'comment' && 'Add Comment'}
                    {actionMode === 'edit' && 'Suggest Edit'}
                    {actionMode === 'flag' && 'Flag Content'}
                  </span>
                </div>
                <button
                  onClick={() => {
                    setActionMode('none')
                    setInputValue('')
                  }}
                  className="p-1 rounded hover:bg-white/10 transition-colors"
                  style={{ color: theme.colors.gray }}
                >
                  <X size={14} />
                </button>
              </div>

              {/* Selected Text Preview */}
              <div
                className="p-2 rounded-lg mb-3 text-xs"
                style={{
                  backgroundColor: `${theme.colors.darkBg}80`,
                  color: theme.colors.gray,
                }}
              >
                <span className="font-semibold">Selected:</span>{' '}
                "{selection.text.length > 100 ? selection.text.slice(0, 100) + '...' : selection.text}"
              </div>

              {/* Input */}
              <div className="relative">
                <textarea
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={getActionLabel()}
                  rows={3}
                  className="w-full rounded-lg border px-3 py-2 text-sm resize-none outline-none transition-all"
                  style={{
                    backgroundColor: `${theme.colors.darkBg}50`,
                    borderColor: inputValue ? getActionColor() : theme.colors.border,
                    color: '#fff',
                  }}
                  autoFocus
                />

                {/* AI Assist hint for edit mode */}
                {actionMode === 'edit' && (
                  <div
                    className="absolute bottom-2 left-2 flex items-center gap-1 text-xs"
                    style={{ color: theme.colors.accent }}
                  >
                    <Sparkles size={12} />
                    AI will help refine this
                  </div>
                )}
              </div>

              {/* Submit Button */}
              <div className="flex justify-end mt-3">
                <button
                  onClick={handleSubmit}
                  disabled={!inputValue.trim()}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all disabled:opacity-50"
                  style={{
                    backgroundColor: getActionColor(),
                    color: '#fff',
                  }}
                >
                  <Send size={14} />
                  Submit
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Pointer triangle */}
        <div
          className="absolute left-1/2 -translate-x-1/2 w-3 h-3 rotate-45"
          style={{
            bottom: actionMode === 'none' ? -6 : -6,
            backgroundColor: theme.colors.lightBg,
            borderRight: `1px solid ${theme.colors.border}`,
            borderBottom: `1px solid ${theme.colors.border}`,
          }}
        />
      </motion.div>
    </AnimatePresence>
  )
}

export default AnnotationToolbar
