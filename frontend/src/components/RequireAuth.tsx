import { Navigate, Outlet, useLocation } from 'react-router'

import { ErrorState, LoadingState } from '@/components/PageStates'
import { useCurrentUser, useSetupStatus } from '@/hooks/useAuth'
import { loginPathFor } from '@/lib/redirect'

export interface LoginLocationState {
  sessionEnded?: boolean
}

/**
 * Gate for every page behind the login: setup first (no admin yet), then a session.
 * Without one, it sends you to /login and remembers the page you wanted (`?next=`).
 */
export function RequireAuth() {
  const location = useLocation()
  const setup = useSetupStatus()
  const me = useCurrentUser()

  if (setup.isPending || me.isPending) return <LoadingState className="min-h-svh" />
  if (setup.isError) return <ErrorState error={setup.error} onRetry={() => void setup.refetch()} />
  if (setup.data.setup_required) return <Navigate to="/setup" replace />
  if (me.isError) return <ErrorState error={me.error} onRetry={() => void me.refetch()} />

  const { user, reason } = me.data
  if (user === null) {
    const target =
      reason === 'logged-out' ? '/login' : loginPathFor(`${location.pathname}${location.search}`)
    const state: LoginLocationState = { sessionEnded: reason === 'session-ended' }
    return <Navigate to={target} replace state={state} />
  }
  return <Outlet />
}
