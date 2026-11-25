import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'

import { isApiError } from '@/api/client'
import type { CurrentUser } from '@/api/types'

declare module '@tanstack/react-query' {
  interface Register {
    queryMeta: QueryMeta
    mutationMeta: QueryMeta
  }
}

interface QueryMeta extends Record<string, unknown> {
  /** Login, setup and "who am I": a 401 there is an answer, not an ended session. */
  authFlow?: boolean
}

export const queryKeys = {
  setup: ['setup'] as const,
  me: ['me'] as const,
  categories: ['categories'] as const,
  devices: ['devices'] as const,
  device: (id: string) => ['devices', id] as const,
  links: ['links'] as const,
  settings: ['settings'] as const,
  dashboard: ['dashboard'] as const,
  sessions: ['sessions'] as const,
  about: ['about'] as const,
}

/**
 * How often the device list (and an open device) is loaded again, for the status dots
 * (brief section 3: the frontend polls every 30 s). Paused while the tab is hidden
 * (TanStack Query's default); a query loads again when the tab comes back (owner decision,
 * M6).
 */
export const POLL_INTERVAL_MS = 30_000

/**
 * While a device's check has no result yet (just turned on or changed), the pages poll this
 * often, so its first result appears within seconds instead of at the next 30 s poll (found
 * in the M6 review).
 */
export const WAITING_POLL_INTERVAL_MS = 5_000

/**
 * Who is logged in. `reason` says why nobody is: the session ended (any 401 from the API),
 * or the user logged out. RequireAuth uses it to choose the login page's message.
 */
export interface AuthState {
  user: CurrentUser | null
  reason: 'session-ended' | 'logged-out' | null
}

function isClientError(error: unknown): boolean {
  return isApiError(error) && error.status >= 400 && error.status < 500
}

export function createQueryClient(): QueryClient {
  // Any 401 outside the login flow means the session ended (30 days unused, 90 days after
  // login, logout in another tab, reset-password). RequireAuth then sends you to /login.
  function onError(error: unknown, meta: QueryMeta | undefined): void {
    if (!isApiError(error, 401) || meta?.authFlow) return
    // Already logged out (a query that was still mounted during logout): keep that reason.
    if (client.getQueryData<AuthState>(queryKeys.me)?.user === null) return
    client.setQueryData<AuthState>(queryKeys.me, { user: null, reason: 'session-ended' })
  }

  const client = new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        onError(error, query.meta)
      },
    }),
    mutationCache: new MutationCache({
      onError: (error, _variables, _result, mutation) => {
        onError(error, mutation.meta)
      },
    }),
    defaultOptions: {
      queries: {
        // 4xx answers do not get better by asking again.
        retry: (failureCount, error) => !isClientError(error) && failureCount < 2,
        staleTime: 10_000,
      },
      mutations: { retry: false },
    },
  })
  return client
}
