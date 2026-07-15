import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { useAppStore } from '../../stores/useAppStore'
import { useCurrentTheme } from '../../context/ThemeContext'

export function AppShell() {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen)
  const theme = useCurrentTheme()

  return (
    <div
      className="min-h-screen"
      style={{ backgroundColor: theme.colors.darkBg }}
    >
      <Sidebar />
      <div
        className="transition-all duration-200"
        style={{ marginLeft: sidebarOpen ? 240 : 64 }}
      >
        <TopBar />
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
