import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import mammoth from 'mammoth'
import {
  FileText,
  Download,
  ZoomIn,
  ZoomOut,
  Loader2,
  AlertCircle,
  Maximize2,
  Minimize2,
  RefreshCw,
} from 'lucide-react'
import { useCurrentTheme } from '../../context/ThemeContext'

interface DocumentPreviewProps {
  /** URL or path to the DOCX file */
  documentUrl?: string
  /** Direct ArrayBuffer of DOCX content */
  documentBuffer?: ArrayBuffer
  /** Title to display */
  title?: string
  /** Enable text selection for annotations */
  enableSelection?: boolean
  /** Callback when text is selected */
  onTextSelect?: (selection: TextSelection) => void
  /** Section click handler */
  onSectionClick?: (sectionId: string) => void
  /** Height of the preview container */
  height?: string
  /** Show download button */
  showDownload?: boolean
  /** Download filename */
  downloadFilename?: string
}

export interface TextSelection {
  text: string
  startOffset: number
  endOffset: number
  rect: DOMRect
  sectionId?: string
}

/**
 * DocumentPreview Component
 * Converts DOCX to HTML using Mammoth.js for in-browser preview
 * Supports text selection, zooming, and section highlighting
 */
export function DocumentPreview({
  documentUrl,
  documentBuffer,
  title = 'Document Preview',
  enableSelection = true,
  onTextSelect,
  onSectionClick,
  height = '600px',
  showDownload = true,
  downloadFilename = 'document.docx',
}: DocumentPreviewProps) {
  const theme = useCurrentTheme()
  const containerRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)

  const [htmlContent, setHtmlContent] = useState<string>('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [zoom, setZoom] = useState(100)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [selection, setSelection] = useState<TextSelection | null>(null)

  // Convert DOCX to HTML
  const convertDocx = useCallback(async (buffer: ArrayBuffer) => {
    setIsLoading(true)
    setError(null)

    try {
      const result = await mammoth.convertToHtml(
        { arrayBuffer: buffer },
        {
          styleMap: [
            "p[style-name='Heading 1'] => h1.doc-h1",
            "p[style-name='Heading 2'] => h2.doc-h2",
            "p[style-name='Heading 3'] => h3.doc-h3",
            "p[style-name='Title'] => h1.doc-title",
            "p[style-name='Normal'] => p.doc-paragraph",
          ],
        }
      )

      // Add section data attributes for targeting
      let processedHtml = result.value
      let sectionCounter = 0
      processedHtml = processedHtml.replace(/<h([123])([^>]*)>/g, (_match, level, attrs) => {
        sectionCounter++
        return `<h${level}${attrs} data-section-id="section-${sectionCounter}">`
      })

      setHtmlContent(processedHtml)

      if (result.messages.length > 0) {
        console.warn('Mammoth conversion warnings:', result.messages)
      }
    } catch (err) {
      console.error('DOCX conversion error:', err)
      setError('Failed to convert document. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Load document from URL
  const loadFromUrl = useCallback(async (url: string) => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error(`Failed to fetch document: ${response.statusText}`)
      }
      const buffer = await response.arrayBuffer()
      await convertDocx(buffer)
    } catch (err) {
      console.error('Document load error:', err)
      setError('Failed to load document. Please check the URL and try again.')
      setIsLoading(false)
    }
  }, [convertDocx])

  // Load document on mount or when source changes
  useEffect(() => {
    if (documentBuffer) {
      convertDocx(documentBuffer)
    } else if (documentUrl) {
      loadFromUrl(documentUrl)
    }
  }, [documentUrl, documentBuffer, convertDocx, loadFromUrl])

  // Handle text selection
  const handleMouseUp = useCallback(() => {
    if (!enableSelection || !contentRef.current) return

    const windowSelection = window.getSelection()
    if (!windowSelection || windowSelection.isCollapsed) {
      setSelection(null)
      return
    }

    const selectedText = windowSelection.toString().trim()
    if (!selectedText) {
      setSelection(null)
      return
    }

    const range = windowSelection.getRangeAt(0)
    const rect = range.getBoundingClientRect()

    // Try to find the section ID
    let sectionId: string | undefined
    let element = range.startContainer.parentElement
    while (element && element !== contentRef.current) {
      if (element.dataset?.sectionId) {
        sectionId = element.dataset.sectionId
        break
      }
      element = element.parentElement
    }

    const newSelection: TextSelection = {
      text: selectedText,
      startOffset: range.startOffset,
      endOffset: range.endOffset,
      rect,
      sectionId,
    }

    setSelection(newSelection)
    onTextSelect?.(newSelection)
  }, [enableSelection, onTextSelect])

  // Handle section clicks
  const handleContentClick = useCallback((e: React.MouseEvent) => {
    const target = e.target as HTMLElement
    let element: HTMLElement | null = target

    while (element && element !== contentRef.current) {
      if (element.dataset?.sectionId) {
        onSectionClick?.(element.dataset.sectionId)
        break
      }
      element = element.parentElement
    }
  }, [onSectionClick])

  // Zoom controls
  const handleZoomIn = () => setZoom(prev => Math.min(prev + 10, 200))
  const handleZoomOut = () => setZoom(prev => Math.max(prev - 10, 50))
  const handleZoomReset = () => setZoom(100)

  // Fullscreen toggle
  const toggleFullscreen = () => {
    if (!containerRef.current) return

    if (!isFullscreen) {
      containerRef.current.requestFullscreen?.()
      setIsFullscreen(true)
    } else {
      document.exitFullscreen?.()
      setIsFullscreen(false)
    }
  }

  // Download handler
  const handleDownload = () => {
    if (documentUrl) {
      const link = document.createElement('a')
      link.href = documentUrl
      link.download = downloadFilename
      link.click()
    } else if (documentBuffer) {
      const blob = new Blob([documentBuffer], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = downloadFilename
      link.click()
      URL.revokeObjectURL(url)
    }
  }

  // Reload document
  const handleReload = () => {
    if (documentBuffer) {
      convertDocx(documentBuffer)
    } else if (documentUrl) {
      loadFromUrl(documentUrl)
    }
  }

  return (
    <div
      ref={containerRef}
      className="rounded-xl overflow-hidden flex flex-col"
      style={{
        backgroundColor: theme.colors.lightBg,
        border: `1px solid ${theme.colors.border}`,
        height: isFullscreen ? '100vh' : height,
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b shrink-0"
        style={{
          backgroundColor: `${theme.colors.darkBg}80`,
          borderColor: theme.colors.border,
        }}
      >
        <div className="flex items-center gap-3">
          <FileText size={18} style={{ color: theme.colors.primary }} />
          <span className="font-medium" style={{ color: '#fff' }}>
            {title}
          </span>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          {/* Zoom Controls */}
          <div
            className="flex items-center gap-1 px-2 py-1 rounded-lg"
            style={{ backgroundColor: `${theme.colors.border}30` }}
          >
            <button
              onClick={handleZoomOut}
              className="p-1 rounded hover:bg-white/10 transition-colors"
              title="Zoom out"
            >
              <ZoomOut size={16} style={{ color: theme.colors.gray }} />
            </button>
            <button
              onClick={handleZoomReset}
              className="px-2 text-sm font-mono hover:bg-white/10 rounded transition-colors"
              style={{ color: theme.colors.gray }}
              title="Reset zoom"
            >
              {zoom}%
            </button>
            <button
              onClick={handleZoomIn}
              className="p-1 rounded hover:bg-white/10 transition-colors"
              title="Zoom in"
            >
              <ZoomIn size={16} style={{ color: theme.colors.gray }} />
            </button>
          </div>

          {/* Reload */}
          <button
            onClick={handleReload}
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
            title="Reload document"
          >
            <RefreshCw size={16} style={{ color: theme.colors.gray }} />
          </button>

          {/* Fullscreen */}
          <button
            onClick={toggleFullscreen}
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
            title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            {isFullscreen ? (
              <Minimize2 size={16} style={{ color: theme.colors.gray }} />
            ) : (
              <Maximize2 size={16} style={{ color: theme.colors.gray }} />
            )}
          </button>

          {/* Download */}
          {showDownload && (documentUrl || documentBuffer) && (
            <button
              onClick={handleDownload}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors"
              style={{
                backgroundColor: `${theme.colors.primary}20`,
                color: theme.colors.primary,
              }}
            >
              <Download size={16} />
              <span className="text-sm">Download</span>
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto relative">
        {/* Loading State */}
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-10">
            <div className="text-center">
              <Loader2
                size={40}
                className="animate-spin mx-auto mb-3"
                style={{ color: theme.colors.primary }}
              />
              <p style={{ color: theme.colors.gray }}>Loading document...</p>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div
              className="text-center p-6 rounded-lg max-w-md"
              style={{
                backgroundColor: `${theme.colors.error}20`,
                border: `1px solid ${theme.colors.error}40`,
              }}
            >
              <AlertCircle
                size={40}
                className="mx-auto mb-3"
                style={{ color: theme.colors.error }}
              />
              <p className="font-semibold mb-2" style={{ color: theme.colors.error }}>
                Error Loading Document
              </p>
              <p className="text-sm" style={{ color: theme.colors.gray }}>
                {error}
              </p>
              <button
                onClick={handleReload}
                className="mt-4 px-4 py-2 rounded-lg text-sm"
                style={{
                  backgroundColor: theme.colors.error,
                  color: '#fff',
                }}
              >
                Try Again
              </button>
            </div>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && !htmlContent && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <FileText
                size={60}
                className="mx-auto mb-4"
                style={{ color: theme.colors.border }}
              />
              <p style={{ color: theme.colors.gray }}>
                No document loaded
              </p>
            </div>
          </div>
        )}

        {/* Document Content */}
        {htmlContent && (
          <div
            ref={contentRef}
            className="p-8 min-h-full"
            style={{
              backgroundColor: '#fff',
              color: '#1a1a1a',
              transform: `scale(${zoom / 100})`,
              transformOrigin: 'top left',
              width: `${10000 / zoom}%`,
            }}
            onMouseUp={handleMouseUp}
            onClick={handleContentClick}
            dangerouslySetInnerHTML={{ __html: htmlContent }}
          />
        )}

        {/* Selection indicator */}
        <AnimatePresence>
          {selection && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              className="fixed bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg text-sm z-20"
              style={{
                backgroundColor: theme.colors.primary,
                color: '#fff',
                boxShadow: `0 4px 20px ${theme.colors.primary}50`,
              }}
            >
              Text selected: "{selection.text.slice(0, 50)}..."
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Document Styles */}
      <style>{`
        .doc-title {
          font-size: 24px;
          font-weight: bold;
          margin-bottom: 16px;
          color: #1a1a1a;
        }
        .doc-h1 {
          font-size: 20px;
          font-weight: bold;
          margin-top: 24px;
          margin-bottom: 12px;
          color: #1a1a1a;
          border-bottom: 1px solid #e0e0e0;
          padding-bottom: 8px;
        }
        .doc-h2 {
          font-size: 18px;
          font-weight: 600;
          margin-top: 20px;
          margin-bottom: 10px;
          color: #333;
        }
        .doc-h3 {
          font-size: 16px;
          font-weight: 600;
          margin-top: 16px;
          margin-bottom: 8px;
          color: #444;
        }
        .doc-paragraph {
          margin-bottom: 12px;
          line-height: 1.6;
        }
        [data-section-id]:hover {
          background-color: rgba(0, 217, 255, 0.1);
          cursor: pointer;
        }
        table {
          width: 100%;
          border-collapse: collapse;
          margin: 16px 0;
        }
        th, td {
          border: 1px solid #ddd;
          padding: 8px 12px;
          text-align: left;
        }
        th {
          background-color: #f5f5f5;
          font-weight: 600;
        }
        tr:nth-child(even) {
          background-color: #fafafa;
        }
      `}</style>
    </div>
  )
}

export default DocumentPreview
