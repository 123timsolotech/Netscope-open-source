import { api, isApiError } from '@/api/client'
import type {
  CurrentUser,
  LoginRequest,
  PasswordChange,
  Sessions,
  SetupRequest,
  SetupStatus,
} from '@/api/types'

export function getSetupStatus(signal?: AbortSignal): Promise<SetupStatus> {
  return api.get<SetupStatus>('/setup', signal)
}

/** Creates the admin and logs in (the answer sets the session cookie). */
export function completeSetup(body: SetupRequest): Promise<CurrentUser> {
  return api.post<CurrentUser>('/setup', body)
}

export function login(body: LoginRequest): Promise<CurrentUser> {
  return api.post<CurrentUser>('/auth/login', body)
}

/** Logs out. A 401 means the session had already ended, which is just as good. */
export async function logout(): Promise<void> {
  try {
    await api.post('/auth/logout', {})
  } catch (error) {
    if (!isApiError(error, 401)) throw error
  }
}

/** The logged-in user, or null when there is no valid session. */
export async function getCurrentUser(signal?: AbortSignal): Promise<CurrentUser | null> {
  try {
    return await api.get<CurrentUser>('/auth/me', signal)
  } catch (error) {
    if (isApiError(error, 401)) return null
    throw error
  }
}

/**
 * Settings → Account (M8). A wrong current password is a 422 on `current_password` (5 a
 * minute, then 429). The answer sets a new session cookie for this browser; every other
 * session ends.
 */
export function changePassword(body: PasswordChange): Promise<CurrentUser> {
  return api.post<CurrentUser>('/auth/password', body)
}

/** How many other sessions of the admin are logged in. */
export function getSessions(signal?: AbortSignal): Promise<Sessions> {
  return api.get<Sessions>('/auth/sessions', signal)
}

/** Ends every other session; this one stays. */
export function logoutOthers(): Promise<Sessions> {
  return api.post<Sessions>('/auth/logout-others', {})
}
