import { useThemeStore } from '../stores/useThemeStore'
import { useTheme, useCurrentTheme } from '../context/ThemeContext'
import { ChevronDown, RotateCcw, Check } from 'lucide-react'
import { useState } from 'react'
import { getThemesWithMetadata } from '../themes'

interface ThemeSwitcherProps {
  variant?: 'dropdown' | 'inline' | 'compact' | 'cards'
}

/**
 * ThemeSwitcher Component
 * Allows users to switch between available themes with visual preview
 */
export function ThemeSwitcher({ variant = 'dropdown' }: ThemeSwitcherProps) {
  const { themeName, switchTheme } = useTheme()
  const currentTheme = useCurrentTheme()
  const store = useThemeStore()
  const [isOpen, setIsOpen] = useState(false)

  const themesWithMeta = getThemesWithMetadata()

  const handleThemeChange = (newThemeName: string) => {
    switchTheme(newThemeName)
    setIsOpen(false)
  }

  const canRevert = store.previousThemeName !== themeName && store.previousThemeName !== undefined

  // New cards variant - beautiful visual theme selector
  if (variant === 'cards') {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {themesWithMeta.map(({ key, theme, icon, label, description }) => {
          const isActive = themeName === key
          return (
            <button
              key={key}
              onClick={() => handleThemeChange(key)}
              className="relative p-4 rounded-xl border-2 text-left transition-all duration-200 hover:scale-[1.02]"
              style={{
                backgroundColor: theme.colors.darkBg,
                borderColor: isActive ? theme.colors.primary : theme.colors.border,
                boxShadow: isActive ? `0 0 20px ${theme.colors.primary}40` : 'none',
              }}
            >
              {/* Active indicator */}
              {isActive && (
                <div
                  className="absolute top-3 right-3 w-6 h-6 rounded-full flex items-center justify-center"
                  style={{ backgroundColor: theme.colors.primary }}
                >
                  <Check size={14} color="#fff" strokeWidth={3} />
                </div>
              )}

              {/* Theme preview colors */}
              <div className="flex gap-2 mb-3">
                <div
                  className="w-8 h-8 rounded-lg"
                  style={{ backgroundColor: theme.colors.primary }}
                  title="Primary"
                />
                <div
                  className="w-8 h-8 rounded-lg"
                  style={{ backgroundColor: theme.colors.secondary }}
                  title="Secondary"
                />
                <div
                  className="w-8 h-8 rounded-lg"
                  style={{ backgroundColor: theme.colors.success }}
                  title="Success"
                />
                <div
                  className="w-8 h-8 rounded-lg border"
                  style={{
                    backgroundColor: theme.colors.lightBg,
                    borderColor: theme.colors.border,
                  }}
                  title="Background"
                />
              </div>

              {/* Theme info */}
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xl">{icon}</span>
                <span
                  className="font-bold text-base"
                  style={{ color: theme.colors.primary }}
                >
                  {label}
                </span>
              </div>
              <p
                className="text-xs"
                style={{ color: theme.colors.gray }}
              >
                {description}
              </p>

              {/* Font preview */}
              <div
                className="mt-3 pt-3 border-t text-xs"
                style={{
                  borderColor: theme.colors.border,
                  color: theme.colors.gray,
                  fontFamily: theme.typography.fontFamily,
                }}
              >
                Font: {theme.typography.fontFamily.split(',')[0].replace(/"/g, '')}
              </div>
            </button>
          )
        })}
      </div>
    )
  }

  if (variant === 'compact') {
    return (
      <div className="flex items-center gap-2">
        <select
          value={themeName}
          onChange={(e) => handleThemeChange(e.target.value)}
          className="px-3 py-2 rounded-md border text-sm font-medium focus:outline-none focus:ring-2"
          style={{
            backgroundColor: currentTheme.colors.lightBg,
            borderColor: currentTheme.colors.border,
            color: currentTheme.colors.gray,
          }}
        >
          {themesWithMeta.map(({ key, label }) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        {canRevert && (
          <button
            onClick={() => store.revertToPrevious()}
            className="p-2 rounded-md border hover:opacity-80 text-sm"
            style={{
              borderColor: currentTheme.colors.border,
              color: currentTheme.colors.gray,
            }}
            title="Revert to previous theme"
          >
            <RotateCcw size={16} />
          </button>
        )}
      </div>
    )
  }

  if (variant === 'inline') {
    return (
      <div className="flex flex-wrap gap-2">
        {themesWithMeta.map(({ key, theme, icon, label }) => {
          const isActive = themeName === key
          return (
            <button
              key={key}
              onClick={() => handleThemeChange(key)}
              className="px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2"
              style={{
                backgroundColor: isActive ? theme.colors.primary : theme.colors.lightBg,
                color: isActive ? '#fff' : theme.colors.gray,
                border: `1px solid ${isActive ? theme.colors.primary : theme.colors.border}`,
                boxShadow: isActive ? `0 4px 12px ${theme.colors.primary}40` : 'none',
              }}
            >
              <span>{icon}</span>
              <span>{label}</span>
            </button>
          )
        })}
      </div>
    )
  }

  // Default dropdown variant
  return (
    <div className="relative inline-block">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2 rounded-lg border font-medium transition-colors"
        style={{
          backgroundColor: currentTheme.colors.lightBg,
          borderColor: currentTheme.colors.border,
          color: currentTheme.colors.gray,
        }}
      >
        Theme:{' '}
        <span className="font-semibold" style={{ color: currentTheme.colors.primary }}>
          {themesWithMeta.find((t) => t.key === themeName)?.label || themeName}
        </span>
        <ChevronDown
          size={16}
          className={`transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {isOpen && (
        <div
          className="absolute right-0 mt-2 w-72 rounded-lg shadow-lg z-50 border"
          style={{
            backgroundColor: currentTheme.colors.darkBg,
            borderColor: currentTheme.colors.border,
          }}
        >
          <div className="p-4 border-b" style={{ borderColor: currentTheme.colors.border }}>
            <h3
              className="font-semibold mb-3"
              style={{ color: currentTheme.colors.primary }}
            >
              Available Themes
            </h3>
            <div className="space-y-2">
              {themesWithMeta.map(({ key, theme, icon, label, description }) => {
                const isActive = themeName === key
                return (
                  <button
                    key={key}
                    onClick={() => handleThemeChange(key)}
                    className="w-full text-left p-3 rounded-lg transition-all"
                    style={{
                      backgroundColor: isActive
                        ? `${theme.colors.primary}20`
                        : 'transparent',
                      border: `1px solid ${isActive ? theme.colors.primary : 'transparent'}`,
                    }}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span>{icon}</span>
                        <span
                          className="font-semibold"
                          style={{ color: theme.colors.primary }}
                        >
                          {label}
                        </span>
                      </div>
                      {isActive && (
                        <Check size={16} style={{ color: theme.colors.primary }} />
                      )}
                    </div>
                    <p className="text-xs" style={{ color: currentTheme.colors.gray }}>
                      {description}
                    </p>
                    {/* Color preview dots */}
                    <div className="flex gap-1 mt-2">
                      <div
                        className="w-4 h-4 rounded-full"
                        style={{ backgroundColor: theme.colors.primary }}
                      />
                      <div
                        className="w-4 h-4 rounded-full"
                        style={{ backgroundColor: theme.colors.secondary }}
                      />
                      <div
                        className="w-4 h-4 rounded-full"
                        style={{ backgroundColor: theme.colors.success }}
                      />
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {canRevert && (
            <div className="p-3 border-t" style={{ borderColor: currentTheme.colors.border }}>
              <button
                onClick={() => {
                  store.revertToPrevious()
                  setIsOpen(false)
                }}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-md transition-colors font-medium text-sm"
                style={{
                  backgroundColor: `${currentTheme.colors.warning}20`,
                  color: currentTheme.colors.warning,
                }}
              >
                <RotateCcw size={14} />
                Revert to Previous
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
