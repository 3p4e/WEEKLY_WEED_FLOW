import { useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useCurrentTheme } from '../../context/ThemeContext'
import { ThemeSwitcher } from '../ThemeSwitcher'
import { LanguageToggle } from '../LanguageToggle'

export function TopBar() {
  const { t } = useTranslation()
  const location = useLocation()
  const theme = useCurrentTheme()

  // Map paths to translation keys
  const getTitleKey = (path: string): string => {
    const pathToKey: Record<string, string> = {
      '/': 'nav.dashboard',
      '/create': 'nav.createSOP',
      '/documents': 'nav.documentLibrary',
      '/knowledge': 'nav.knowledgeBase',
      '/settings': 'nav.settings',
    }
    return pathToKey[path] || 'nav.appTitle'
  }

  const title = t(getTitleKey(location.pathname))

  return (
    <header
      className="h-16 border-b backdrop-blur-sm flex items-center justify-between px-6"
      style={{
        backgroundColor: `${theme.colors.darkBg}80`,
        borderBottomColor: theme.colors.border,
      }}
    >
      <h1
        className="text-lg font-semibold"
        style={{ color: theme.colors.lightBg }}
      >
        {title}
      </h1>
      <div className="flex items-center gap-3">
        <LanguageToggle variant="compact" />
        <ThemeSwitcher variant="compact" />
      </div>
    </header>
  )
}
