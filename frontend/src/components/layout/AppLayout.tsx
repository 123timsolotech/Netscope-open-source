import {
  LayoutDashboard,
  LogOut,
  Menu,
  Network,
  Server,
  Settings,
  type LucideIcon,
} from 'lucide-react'
import { useRef, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Logo } from '@/components/layout/Logo'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { UnsavedChangesContext, useUnsavedChangesRegistry } from '@/hooks/unsavedChanges'
import { useCurrentUser, useLogout } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

// Only pages that exist (decision M4); the Dashboard first, since M7.
const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/devices', label: 'Devices', icon: Server },
  { to: '/topology', label: 'Topology', icon: Network },
  { to: '/settings', label: 'Settings', icon: Settings },
]

function useLogoutAction(): { logout: () => void; pending: boolean } {
  const navigate = useNavigate()
  const mutation = useLogout()
  return {
    pending: mutation.isPending,
    logout: () => {
      mutation.mutate(undefined, {
        onSuccess: () => void navigate('/login', { replace: true }),
        onError: (error) => toast.error(`Could not log out: ${error.message}`),
      })
    },
  }
}

export function AppLayout() {
  const me = useCurrentUser()
  const username = me.data?.user?.username ?? ''
  const { logout: logoutNow, pending } = useLogoutAction()
  const unsaved = useUnsavedChangesRegistry()
  const [confirmLogout, setConfirmLogout] = useState(false)
  // Focus after the logout prompt when it was opened from the (now closed) mobile menu.
  const menuButton = useRef<HTMLButtonElement | null>(null)

  // Logging out unmounts the page at once, so the router's unsaved-changes prompt cannot run.
  function logout() {
    if (unsaved.hasUnsavedChanges()) setConfirmLogout(true)
    else logoutNow()
  }

  return (
    <UnsavedChangesContext value={unsaved}>
      <div className="min-h-svh md:grid md:grid-cols-[14rem_1fr]">
        {/* Desktop: sidebar */}
        <aside className="sticky top-0 hidden h-svh flex-col border-r bg-sidebar p-3 md:flex">
          <Logo className="px-2 py-3" />
          <nav aria-label="Main" className="mt-4 grid gap-1">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2 rounded-md px-2 py-2 text-sm text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-foreground',
                    isActive && 'bg-sidebar-accent font-medium text-sidebar-foreground',
                  )
                }
              >
                <item.icon aria-hidden="true" className="size-4" />
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="mt-auto grid gap-2 border-t pt-3">
            <p
              title={`Logged in as ${username}`}
              className="truncate px-2 text-sm text-muted-foreground"
            >
              Logged in as{' '}
              <span dir="auto" className="text-foreground">
                {username}
              </span>
            </p>
            <Button variant="ghost" className="justify-start" disabled={pending} onClick={logout}>
              <LogOut aria-hidden="true" />
              Log out
            </Button>
          </div>
        </aside>

        {/* Mobile: top bar with a menu */}
        <header className="sticky top-0 z-40 flex items-center justify-between border-b bg-sidebar px-4 py-2 md:hidden">
          <Logo />
          <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>
              <Button ref={menuButton} variant="ghost" size="icon" aria-label="Open menu">
                <Menu />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel
                title={`Logged in as ${username}`}
                className="truncate font-normal text-muted-foreground"
              >
                Logged in as{' '}
                <span dir="auto" className="text-foreground">
                  {username}
                </span>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              {NAV_ITEMS.map((item) => (
                <DropdownMenuItem key={item.to} asChild>
                  <NavLink to={item.to}>
                    <item.icon aria-hidden="true" />
                    {item.label}
                  </NavLink>
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
              <DropdownMenuItem disabled={pending} onSelect={logout}>
                <LogOut aria-hidden="true" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>

        <main className="min-w-0 p-4 md:p-8">
          <Outlet />
        </main>

        <ConfirmDialog
          open={confirmLogout}
          returnFocus={() => menuButton.current}
          onOpenChange={setConfirmLogout}
          title="Log out without saving?"
          description="Your changes on this page will be lost."
          confirmLabel="Log out"
          onConfirm={() => {
            setConfirmLogout(false)
            logoutNow()
          }}
        />
      </div>
    </UnsavedChangesContext>
  )
}
