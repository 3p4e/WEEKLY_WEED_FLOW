import { useTranslation } from 'react-i18next'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { ThemeSwitcher } from '../components/ThemeSwitcher'
import { LanguageToggle } from '../components/LanguageToggle'
import { useCurrentTheme } from '../context/ThemeContext'
import { useThemeStore } from '../stores/useThemeStore'
import { Palette, Info, Globe } from 'lucide-react'

export default function SettingsPage() {
  const { t } = useTranslation()
  const theme = useCurrentTheme()
  const store = useThemeStore()

  return (
    <div className="max-w-2xl space-y-6">
      {/* Language Settings */}
      <Card>
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Globe size={20} style={{ color: theme.colors.accent }} />
            <h3
              className="text-lg font-semibold"
              style={{ color: theme.colors.accent }}
            >
              {t('language.selectLanguage')}
            </h3>
          </div>
          <p style={{ color: theme.colors.gray }} className="text-sm">
            {t('settings.customizeAppearance')}
          </p>
        </div>

        <div className="max-w-xs">
          <LanguageToggle variant="dropdown" />
        </div>

        <p className="text-xs mt-4" style={{ color: theme.colors.gray }}>
          Note: Language selection affects only the user interface. Document generation always remains in English for regulatory compliance.
        </p>
      </Card>

      {/* Appearance & Theme Settings */}
      <Card>
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Palette size={20} style={{ color: theme.colors.primary }} />
            <h3
              className="text-lg font-semibold"
              style={{ color: theme.colors.primary }}
            >
              {t('settings.appearanceTheme')}
            </h3>
          </div>
          <p style={{ color: theme.colors.gray }} className="text-sm">
            {t('settings.customizeAppearance')}
          </p>
        </div>

        <div className="space-y-6">
          {/* Theme Selector - Cards */}
          <div>
            <label
              className="block text-sm font-semibold mb-4"
              style={{ color: theme.colors.primary }}
            >
              {t('settings.selectTheme')}
            </label>
            <ThemeSwitcher variant="cards" />
            <p className="text-xs mt-3" style={{ color: theme.colors.gray }}>
              {t('settings.themeSelectionNote')}
            </p>
          </div>

          {/* Current Theme Info */}
          <div
            className="p-4 rounded-lg border"
            style={{
              backgroundColor: theme.colors.lightBg,
              borderColor: theme.colors.border,
            }}
          >
            <h4
              className="text-sm font-semibold mb-2"
              style={{ color: theme.colors.primary }}
            >
              {t('settings.currentTheme')}
            </h4>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span style={{ color: theme.colors.gray }} className="block text-xs mb-1">
                  {t('settings.themeName')}
                </span>
                <span
                  className="font-semibold"
                  style={{ color: theme.colors.secondary }}
                >
                  {store.currentThemeName}
                </span>
              </div>
              <div>
                <span style={{ color: theme.colors.gray }} className="block text-xs mb-1">
                  {t('settings.description')}
                </span>
                <span
                  className="font-semibold"
                  style={{ color: theme.colors.gray }}
                >
                  {theme.description}
                </span>
              </div>
            </div>
          </div>

          {/* Revert Options */}
          {store.previousThemeName && store.previousThemeName !== store.currentThemeName && (
            <div
              className="p-4 rounded-lg border flex items-center justify-between"
              style={{
                backgroundColor: `${theme.colors.warning}10`,
                borderColor: theme.colors.warning,
              }}
            >
              <div>
                <p className="text-sm font-semibold" style={{ color: theme.colors.warning }}>
                  {t('settings.revertTheme')}
                </p>
                <p className="text-xs" style={{ color: theme.colors.gray }}>
                  {t('settings.switchBackTo', { theme: store.previousThemeName })}
                </p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => store.revertToPrevious()}
              >
                {t('common.revert')}
              </Button>
            </div>
          )}

          {store.currentThemeName !== store.defaultThemeName && (
            <div
              className="p-4 rounded-lg border flex items-center justify-between"
              style={{
                backgroundColor: `${theme.colors.info}10`,
                borderColor: theme.colors.info,
              }}
            >
              <div>
                <p className="text-sm font-semibold" style={{ color: theme.colors.info }}>
                  {t('settings.resetToDefault')}
                </p>
                <p className="text-xs" style={{ color: theme.colors.gray }}>
                  {t('settings.restoreTheme')}
                </p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => store.resetToDefault()}
              >
                {t('common.reset')}
              </Button>
            </div>
          )}
        </div>
      </Card>

      {/* Color Palette Reference */}
      <Card>
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Info size={20} style={{ color: theme.colors.secondary }} />
            <h3
              className="text-lg font-semibold"
              style={{ color: theme.colors.secondary }}
            >
              {t('settings.colorPalette')}
            </h3>
          </div>
          <p style={{ color: theme.colors.gray }} className="text-sm">
            {t('settings.colorPaletteNote')}
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {Object.entries(theme.colors).map(([name, color]) => (
            <div
              key={name}
              className="p-3 rounded-lg border"
              style={{
                backgroundColor: theme.colors.lightBg,
                borderColor: theme.colors.border,
              }}
            >
              <div
                className="w-full h-12 rounded mb-2 border"
                style={{
                  backgroundColor: color,
                  borderColor: theme.colors.border,
                }}
              />
              <p className="text-xs font-mono" style={{ color: theme.colors.gray }}>
                {name}
              </p>
              <p className="text-xs font-mono" style={{ color: theme.colors.gray }}>
                {color}
              </p>
            </div>
          ))}
        </div>
      </Card>

      {/* Backend Configuration */}
      <Card>
        <h3
          className="text-lg font-semibold mb-4"
          style={{ color: theme.colors.primary }}
        >
          {t('settings.backendConfig')}
        </h3>
        <div className="space-y-3 text-sm">
          <div
            className="flex justify-between p-3 rounded-lg"
            style={{ backgroundColor: theme.colors.lightBg }}
          >
            <span style={{ color: theme.colors.gray }}>{t('settings.apiUrl')}</span>
            <span
              className="font-mono font-semibold"
              style={{ color: theme.colors.secondary }}
            >
              http://localhost:8000
            </span>
          </div>
          <div
            className="flex justify-between p-3 rounded-lg"
            style={{ backgroundColor: theme.colors.lightBg }}
          >
            <span style={{ color: theme.colors.gray }}>{t('settings.lettaServer')}</span>
            <span
              className="font-mono font-semibold"
              style={{ color: theme.colors.secondary }}
            >
              http://localhost:8283
            </span>
          </div>
        </div>
      </Card>
    </div>
  )
}
