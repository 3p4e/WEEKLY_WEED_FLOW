import { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown } from 'lucide-react'
import { useCurrentTheme } from '../context/ThemeContext'
import { LANGUAGES, setLanguage, getCurrentLanguage, type LanguageCode } from '../i18n'

// UK Flag SVG Component (Union Jack)
function UKFlag({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 60 30"
      className={className}
      style={{ borderRadius: '2px' }}
    >
      {/* Blue background */}
      <clipPath id="uk-s">
        <path d="M0,0 v30 h60 v-30 z" />
      </clipPath>
      <clipPath id="uk-t">
        <path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z" />
      </clipPath>
      <g clipPath="url(#uk-s)">
        <path d="M0,0 v30 h60 v-30 z" fill="#012169" />
        <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" strokeWidth="6" />
        <path d="M0,0 L60,30 M60,0 L0,30" clipPath="url(#uk-t)" stroke="#C8102E" strokeWidth="4" />
        <path d="M30,0 v30 M0,15 h60" stroke="#fff" strokeWidth="10" />
        <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth="6" />
      </g>
    </svg>
  )
}

// Macedonian Flag SVG Component (Vergina Sun)
function MacedonianFlag({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 60 30"
      className={className}
      style={{ borderRadius: '2px' }}
    >
      {/* Red background */}
      <rect width="60" height="30" fill="#D20000" />
      {/* Yellow sun with 8 rays */}
      <g fill="#FFE600">
        {/* Center circle */}
        <circle cx="30" cy="15" r="3.5" />
        {/* 8 rays extending to edges */}
        <polygon points="30,0 26,15 30,15 34,15" />
        <polygon points="30,30 26,15 30,15 34,15" />
        <polygon points="0,15 30,11 30,15 30,19" />
        <polygon points="60,15 30,11 30,15 30,19" />
        {/* Diagonal rays */}
        <polygon points="8.79,4.39 26.5,13.5 30,15 28.5,11.5" />
        <polygon points="51.21,25.61 33.5,16.5 30,15 31.5,18.5" />
        <polygon points="51.21,4.39 33.5,13.5 30,15 31.5,11.5" />
        <polygon points="8.79,25.61 26.5,16.5 30,15 28.5,18.5" />
      </g>
    </svg>
  )
}

interface LanguageToggleProps {
  variant?: 'dropdown' | 'compact'
}

export function LanguageToggle({ variant = 'dropdown' }: LanguageToggleProps) {
  const { t } = useTranslation()
  const theme = useCurrentTheme()
  const [isOpen, setIsOpen] = useState(false)
  const [currentLang, setCurrentLang] = useState<LanguageCode>(getCurrentLanguage())
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleLanguageChange = (lang: LanguageCode) => {
    setLanguage(lang)
    setCurrentLang(lang)
    setIsOpen(false)
  }

  const FlagComponent = currentLang === 'en' ? UKFlag : MacedonianFlag
  const currentLanguage = LANGUAGES[currentLang]

  if (variant === 'compact') {
    return (
      <div ref={dropdownRef} className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-2 px-3 py-2 rounded-lg transition-all"
          style={{
            backgroundColor: `${theme.colors.lightBg}50`,
            border: `1px solid ${theme.colors.border}`,
          }}
          title={t('language.selectLanguage')}
          aria-label={t('language.selectLanguage')}
        >
          <FlagComponent className="w-5 h-3" />
          <ChevronDown
            size={14}
            className={`transition-transform ${isOpen ? 'rotate-180' : ''}`}
            style={{ color: theme.colors.gray }}
          />
        </button>

        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, y: -5, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -5, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="absolute right-0 mt-2 py-1 rounded-lg shadow-lg z-50 min-w-[160px]"
              style={{
                backgroundColor: theme.colors.lightBg,
                border: `1px solid ${theme.colors.border}`,
                boxShadow: `0 10px 40px ${theme.colors.darkBg}80`,
              }}
            >
              {(Object.keys(LANGUAGES) as LanguageCode[]).map((lang) => {
                const langInfo = LANGUAGES[lang]
                const isSelected = lang === currentLang
                const Flag = lang === 'en' ? UKFlag : MacedonianFlag

                return (
                  <button
                    key={lang}
                    onClick={() => handleLanguageChange(lang)}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors"
                    style={{
                      backgroundColor: isSelected ? `${theme.colors.primary}20` : 'transparent',
                      color: isSelected ? theme.colors.primary : '#fff',
                    }}
                  >
                    <Flag className="w-6 h-4 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium">{langInfo.nativeName}</div>
                      <div
                        className="text-xs"
                        style={{ color: theme.colors.gray }}
                      >
                        {langInfo.name}
                      </div>
                    </div>
                    {isSelected && (
                      <div
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: theme.colors.success }}
                      />
                    )}
                  </button>
                )
              })}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    )
  }

  // Full dropdown variant
  return (
    <div ref={dropdownRef} className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all w-full"
        style={{
          backgroundColor: `${theme.colors.lightBg}50`,
          border: `1px solid ${theme.colors.border}`,
        }}
      >
        <FlagComponent className="w-6 h-4" />
        <span className="flex-1 text-left text-sm font-medium" style={{ color: '#fff' }}>
          {currentLanguage.nativeName}
        </span>
        <ChevronDown
          size={16}
          className={`transition-transform ${isOpen ? 'rotate-180' : ''}`}
          style={{ color: theme.colors.gray }}
        />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -5, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -5, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute left-0 right-0 mt-2 py-1 rounded-lg shadow-lg z-50"
            style={{
              backgroundColor: theme.colors.lightBg,
              border: `1px solid ${theme.colors.border}`,
              boxShadow: `0 10px 40px ${theme.colors.darkBg}80`,
            }}
          >
            <div
              className="px-4 py-2 text-xs font-semibold uppercase tracking-wide"
              style={{
                color: theme.colors.gray,
                borderBottom: `1px solid ${theme.colors.border}`,
              }}
            >
              {t('language.selectLanguage')}
            </div>

            {(Object.keys(LANGUAGES) as LanguageCode[]).map((lang) => {
              const langInfo = LANGUAGES[lang]
              const isSelected = lang === currentLang
              const Flag = lang === 'en' ? UKFlag : MacedonianFlag

              return (
                <button
                  key={lang}
                  onClick={() => handleLanguageChange(lang)}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/5"
                  style={{
                    backgroundColor: isSelected ? `${theme.colors.primary}15` : 'transparent',
                  }}
                >
                  <Flag className="w-7 h-5 shrink-0" />
                  <div className="flex-1">
                    <div
                      className="text-sm font-medium"
                      style={{ color: isSelected ? theme.colors.primary : '#fff' }}
                    >
                      {langInfo.nativeName}
                    </div>
                    <div
                      className="text-xs"
                      style={{ color: theme.colors.gray }}
                    >
                      {langInfo.name}
                    </div>
                  </div>
                  {isSelected && (
                    <div
                      className="px-2 py-0.5 rounded text-xs font-medium"
                      style={{
                        backgroundColor: `${theme.colors.success}20`,
                        color: theme.colors.success,
                      }}
                    >
                      {t('language.currentLanguage')}
                    </div>
                  )}
                </button>
              )
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default LanguageToggle
