import { NavLink, Outlet } from 'react-router'

import { useAbout } from '@/hooks/useAbout'
import { cn } from '@/lib/utils'

// The four Settings tabs (owner decision, M8).
const SECTIONS = [
  { to: '/settings/categories', label: 'Categories' },
  { to: '/settings/status-checks', label: 'Status checks' },
  { to: '/settings/account', label: 'Account' },
  { to: '/settings/backup', label: 'Backup' },
]

/** "NetScope 0.1.0" under every Settings page; nothing while loading or when it fails. */
function VersionLine() {
  const about = useAbout()
  if (!about.data) return null
  return <p className="text-xs text-muted-foreground">NetScope {about.data.version}</p>
}

export function SettingsLayout() {
  return (
    <div className="grid gap-6">
      <header className="grid gap-3">
        <h1 className="text-2xl font-semibold">Settings</h1>
        {/* Narrow padding on a phone, so the four tabs fit in one row at 390 px. */}
        <nav aria-label="Settings" className="flex flex-wrap gap-1 border-b">
          {SECTIONS.map((section) => (
            <NavLink
              key={section.to}
              to={section.to}
              className={({ isActive }) =>
                cn(
                  '-mb-px border-b-2 border-transparent px-2 py-2 text-sm whitespace-nowrap text-muted-foreground hover:text-foreground sm:px-3',
                  isActive && 'border-primary text-foreground',
                )
              }
            >
              {section.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <Outlet />
      <footer>
        <VersionLine />
      </footer>
    </div>
  )
}
