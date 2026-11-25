import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import {
  changePassword,
  completeSetup,
  getCurrentUser,
  getSessions,
  getSetupStatus,
  login,
  logout,
  logoutOthers,
} from '@/api/auth'
import type { CurrentUser, Sessions, SetupStatus } from '@/api/types'
import { queryKeys, type AuthState } from '@/hooks/queryClient'

export function useSetupStatus() {
  return useQuery({
    queryKey: queryKeys.setup,
    queryFn: ({ signal }) => getSetupStatus(signal),
    staleTime: Infinity,
    meta: { authFlow: true },
  })
}

export function useCurrentUser() {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: async ({ signal }): Promise<AuthState> => ({
      user: await getCurrentUser(signal),
      reason: null,
    }),
    staleTime: Infinity,
    meta: { authFlow: true },
  })
}

/** Drops everything loaded for the previous session, then remembers the new user. */
function startSession(client: QueryClient, user: CurrentUser): void {
  client.removeQueries({ queryKey: queryKeys.devices })
  client.removeQueries({ queryKey: queryKeys.categories })
  client.setQueryData<AuthState>(queryKeys.me, { user, reason: null })
}

export function useLogin() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: login,
    meta: { authFlow: true },
    onSuccess: (user) => {
      startSession(client, user)
    },
  })
}

export function useCompleteSetup() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: completeSetup,
    meta: { authFlow: true },
    onSuccess: (user) => {
      client.setQueryData<SetupStatus>(queryKeys.setup, { setup_required: false })
      startSession(client, user)
    },
  })
}

export function useLogout() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: logout,
    onSuccess: () => {
      client.setQueryData<AuthState>(queryKeys.me, { user: null, reason: 'logged-out' })
      client.removeQueries({ queryKey: queryKeys.devices })
      client.removeQueries({ queryKey: queryKeys.categories })
    },
  })
}

/** Settings → Account (M8). Every other session ends, so the count is loaded again. */
export function useChangePassword() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: changePassword,
    onSuccess: (user) => {
      client.setQueryData<AuthState>(queryKeys.me, { user, reason: null })
      return client.invalidateQueries({ queryKey: queryKeys.sessions })
    },
  })
}

/** How many other sessions are logged in (Settings → Account). */
export function useSessions() {
  return useQuery({
    queryKey: queryKeys.sessions,
    queryFn: ({ signal }) => getSessions(signal),
  })
}

export function useLogoutOthers() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: logoutOthers,
    onSuccess: (sessions) => {
      client.setQueryData<Sessions>(queryKeys.sessions, sessions)
      return client.invalidateQueries({ queryKey: queryKeys.sessions })
    },
  })
}
