import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import {
  LayoutDashboard,
  FilePlus2,
  FolderOpen,
  Search,
  Settings,
  ChevronLeft,
  Leaf,
} from 'lucide-react'
import { useAppStore } from '../../stores/useAppStore'
import { useCurrentTheme } from '../../context/ThemeContext'

// Navigation items with translation keys
const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, labelKey: 'nav.dashboard' },
  { to: '/create', icon: FilePlus2, labelKey: 'nav.createSOP' },
  { to: '/documents', icon: FolderOpen, labelKey: 'nav.documents' },
  { to: '/knowledge', icon: Search, labelKey: 'nav.knowledge' },
  { to: '/settings', icon: Settings, labelKey: 'nav.settings' },
]

export function Sidebar() {
  const { t } = useTranslation()
  const { sidebarOpen, toggleSidebar } = useAppStore()
  const theme = useCurrentTheme()

  // Calculate theme-aware colors with alpha
  const bgColor = theme.colors.darkBg
  const bgRgba = `${bgColor}40` // Add alpha

  return (
    <motion.aside
      initial={false}
      animate={{ width: sidebarOpen ? 240 : 64 }}
      transition={{ duration: 0.2 }}
      style={{
        backgroundColor: bgRgba,
        borderRightColor: theme.colors.border,
      }}
      className="fixed left-0 top-0 h-screen backdrop-blur-md border-r z-30 flex flex-col"
    >
      {/* Logo */}
      <div
        className="flex items-center gap-3 px-4 h-16 border-b"
        style={{ borderBottomColor: theme.colors.border }}
      >
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
          style={{ backgroundColor: theme.colors.secondary }}
        >
          <Leaf size={18} className="text-white" />
        </div>
        {sidebarOpen && (
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-sm font-semibold whitespace-nowrap"
            style={{ color: theme.colors.lightBg }}
          >
            {t('nav.appTitle')}
          </motion.span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 space-y-1 px-2">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors"
            style={({ isActive }) => ({
              backgroundColor: isActive ? `${theme.colors.secondary}25` : 'transparent',
              color: isActive ? theme.colors.secondary : `${theme.colors.gray}80`,
            })}
          >
            <item.icon size={20} className="shrink-0" />
            {sidebarOpen && <span>{t(item.labelKey)}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Collapse */}
      <button
        type="button"
        onClick={toggleSidebar}
        className="flex items-center justify-center h-12 border-t transition-colors hover:opacity-80"
        style={{
          borderTopColor: theme.colors.border,
          color: theme.colors.gray,
        }}
        title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
        aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
      >
        <ChevronLeft
          size={18}
          className={`transition-transform ${!sidebarOpen ? 'rotate-180' : ''}`}
        />
      </button>
    </motion.aside>
  )
}
