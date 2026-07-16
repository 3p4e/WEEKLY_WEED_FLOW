import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  MessageSquare,
  Edit3,
  Flag,
  Check,
  X,
  Send,
  Trash2,
  Clock,
  User,
  ChevronDown,
} from 'lucide-react'
import { useCurrentTheme } from '../../context/ThemeContext'

export interface Comment {
  id: string
  type: 'comment' | 'edit' | 'flag'
  selectedText: string
  content: string
  author: string
  timestamp: Date
  sectionId?: string
  status: 'pending' | 'resolved' | 'rejected'
  replies: Reply[]
}

export interface Reply {
  id: string
  content: string
  author: string
  timestamp: Date
  isAgentResponse?: boolean
}

interface CommentThreadProps {
  comments: Comment[]
  onResolve: (commentId: string) => void
  onReject: (commentId: string) => void
  onDelete: (commentId: string) => void
  onReply: (commentId: string, content: string) => void
  onCommentClick?: (comment: Comment) => void
}

/**
 * CommentThread Component
 * Displays a list of comments, edits, and flags with reply functionality
 * Shows agent responses and resolution status
 */
export function CommentThread({
  comments,
  onResolve,
  onReject,
  onDelete,
  onReply,
  onCommentClick,
}: CommentThreadProps) {
  const theme = useCurrentTheme()
  const [expandedComments, setExpandedComments] = useState<Set<string>>(new Set())
  const [replyingTo, setReplyingTo] = useState<string | null>(null)
  const [replyContent, setReplyContent] = useState('')

  const toggleExpand = (commentId: string) => {
    setExpandedComments(prev => {
      const newSet = new Set(prev)
      if (newSet.has(commentId)) {
        newSet.delete(commentId)
      } else {
        newSet.add(commentId)
      }
      return newSet
    })
  }

  const handleReply = (commentId: string) => {
    if (replyContent.trim()) {
      onReply(commentId, replyContent)
      setReplyContent('')
      setReplyingTo(null)
    }
  }

  const getTypeIcon = (type: Comment['type']) => {
    switch (type) {
      case 'comment':
        return <MessageSquare size={14} />
      case 'edit':
        return <Edit3 size={14} />
      case 'flag':
        return <Flag size={14} />
    }
  }

  const getTypeColor = (type: Comment['type']) => {
    switch (type) {
      case 'comment':
        return theme.colors.info
      case 'edit':
        return theme.colors.accent
      case 'flag':
        return theme.colors.warning
    }
  }

  const getStatusColor = (status: Comment['status']) => {
    switch (status) {
      case 'resolved':
        return theme.colors.success
      case 'rejected':
        return theme.colors.error
      default:
        return theme.colors.gray
    }
  }

  const formatTime = (date: Date) => {
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(diff / 86400000)

    if (minutes < 1) return 'Just now'
    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    return `${days}d ago`
  }

  if (comments.length === 0) {
    return (
      <div
        className="p-6 text-center rounded-lg"
        style={{
          backgroundColor: `${theme.colors.lightBg}50`,
          border: `1px dashed ${theme.colors.border}`,
        }}
      >
        <MessageSquare
          size={32}
          className="mx-auto mb-3"
          style={{ color: theme.colors.border }}
        />
        <p style={{ color: theme.colors.gray }}>No comments yet</p>
        <p className="text-sm mt-1" style={{ color: theme.colors.gray }}>
          Select text in the document to add comments or suggest edits
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {comments.map((comment) => {
        const isExpanded = expandedComments.has(comment.id)
        const typeColor = getTypeColor(comment.type)
        const statusColor = getStatusColor(comment.status)

        return (
          <motion.div
            key={comment.id}
            layout
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-lg overflow-hidden"
            style={{
              backgroundColor: theme.colors.lightBg,
              border: `1px solid ${theme.colors.border}`,
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-4 py-3 cursor-pointer"
              style={{
                backgroundColor: `${typeColor}10`,
                borderBottom: `1px solid ${theme.colors.border}`,
              }}
              onClick={() => {
                toggleExpand(comment.id)
                onCommentClick?.(comment)
              }}
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center"
                  style={{ backgroundColor: `${typeColor}30`, color: typeColor }}
                >
                  {getTypeIcon(comment.type)}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span
                      className="text-sm font-medium"
                      style={{ color: '#fff' }}
                    >
                      {comment.type === 'comment' && 'Comment'}
                      {comment.type === 'edit' && 'Edit Suggestion'}
                      {comment.type === 'flag' && 'Flagged'}
                    </span>
                    <span
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{
                        backgroundColor: `${statusColor}20`,
                        color: statusColor,
                      }}
                    >
                      {comment.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs" style={{ color: theme.colors.gray }}>
                    <User size={10} />
                    <span>{comment.author}</span>
                    <span>•</span>
                    <Clock size={10} />
                    <span>{formatTime(comment.timestamp)}</span>
                  </div>
                </div>
              </div>

              <ChevronDown
                size={18}
                className={`transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                style={{ color: theme.colors.gray }}
              />
            </div>

            {/* Content */}
            <AnimatePresence>
              {isExpanded && (
                <motion.div
                  initial={{ height: 0 }}
                  animate={{ height: 'auto' }}
                  exit={{ height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="p-4">
                    {/* Selected Text */}
                    <div
                      className="p-3 rounded-lg mb-4 text-sm"
                      style={{
                        backgroundColor: `${theme.colors.darkBg}80`,
                        borderLeft: `3px solid ${typeColor}`,
                      }}
                    >
                      <p className="text-xs mb-1" style={{ color: theme.colors.gray }}>
                        Selected text:
                      </p>
                      <p style={{ color: '#fff' }}>
                        "{comment.selectedText.length > 150
                          ? comment.selectedText.slice(0, 150) + '...'
                          : comment.selectedText}"
                      </p>
                    </div>

                    {/* Comment Content */}
                    <div className="mb-4">
                      <p className="text-sm" style={{ color: '#fff' }}>
                        {comment.content}
                      </p>
                    </div>

                    {/* Replies */}
                    {comment.replies.length > 0 && (
                      <div className="space-y-3 mb-4">
                        <p className="text-xs font-semibold" style={{ color: theme.colors.gray }}>
                          Replies ({comment.replies.length})
                        </p>
                        {comment.replies.map((reply) => (
                          <div
                            key={reply.id}
                            className="pl-4 border-l-2"
                            style={{
                              borderColor: reply.isAgentResponse
                                ? theme.colors.success
                                : theme.colors.border,
                            }}
                          >
                            <div className="flex items-center gap-2 mb-1">
                              <span
                                className="text-xs font-medium"
                                style={{
                                  color: reply.isAgentResponse
                                    ? theme.colors.success
                                    : theme.colors.gray,
                                }}
                              >
                                {reply.author}
                                {reply.isAgentResponse && ' (Agent)'}
                              </span>
                              <span className="text-xs" style={{ color: theme.colors.gray }}>
                                {formatTime(reply.timestamp)}
                              </span>
                            </div>
                            <p className="text-sm" style={{ color: '#fff' }}>
                              {reply.content}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Reply Input */}
                    {replyingTo === comment.id ? (
                      <div className="space-y-2">
                        <textarea
                          value={replyContent}
                          onChange={(e) => setReplyContent(e.target.value)}
                          placeholder="Write a reply..."
                          rows={2}
                          className="w-full rounded-lg border px-3 py-2 text-sm resize-none outline-none"
                          style={{
                            backgroundColor: `${theme.colors.darkBg}50`,
                            borderColor: theme.colors.border,
                            color: '#fff',
                          }}
                          autoFocus
                        />
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => {
                              setReplyingTo(null)
                              setReplyContent('')
                            }}
                            className="px-3 py-1.5 rounded-lg text-sm"
                            style={{ color: theme.colors.gray }}
                          >
                            Cancel
                          </button>
                          <button
                            onClick={() => handleReply(comment.id)}
                            disabled={!replyContent.trim()}
                            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm disabled:opacity-50"
                            style={{
                              backgroundColor: theme.colors.primary,
                              color: '#fff',
                            }}
                          >
                            <Send size={14} />
                            Reply
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        onClick={() => setReplyingTo(comment.id)}
                        className="text-sm"
                        style={{ color: theme.colors.primary }}
                      >
                        + Add reply
                      </button>
                    )}

                    {/* Actions */}
                    {comment.status === 'pending' && (
                      <div
                        className="flex items-center gap-2 mt-4 pt-4 border-t"
                        style={{ borderColor: theme.colors.border }}
                      >
                        <button
                          onClick={() => onResolve(comment.id)}
                          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors"
                          style={{
                            backgroundColor: `${theme.colors.success}20`,
                            color: theme.colors.success,
                          }}
                        >
                          <Check size={14} />
                          Resolve
                        </button>
                        <button
                          onClick={() => onReject(comment.id)}
                          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors"
                          style={{
                            backgroundColor: `${theme.colors.error}20`,
                            color: theme.colors.error,
                          }}
                        >
                          <X size={14} />
                          Reject
                        </button>
                        <div className="flex-1" />
                        <button
                          onClick={() => onDelete(comment.id)}
                          className="p-1.5 rounded-lg transition-colors hover:bg-red-500/20"
                          style={{ color: theme.colors.gray }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )
      })}
    </div>
  )
}

export default CommentThread
