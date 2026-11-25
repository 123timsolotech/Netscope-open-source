import { api } from '@/api/client'
import type { Settings, SettingsUpdate } from '@/api/types'

/** The status check settings in effect (stored values, or the defaults). */
export function getSettings(signal?: AbortSignal): Promise<Settings> {
  return api.get<Settings>('/settings', signal)
}

/** Partial update; the timeout must be at most half the interval (422 otherwise). */
export function updateSettings(body: SettingsUpdate): Promise<Settings> {
  return api.patch<Settings>('/settings', body)
}
