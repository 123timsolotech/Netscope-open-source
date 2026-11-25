import { api } from '@/api/client'
import type { Dashboard } from '@/api/types'

/** Totals, status counts, counts by category, recently edited and down devices (M7). */
export function getDashboard(signal?: AbortSignal): Promise<Dashboard> {
  return api.get<Dashboard>('/dashboard', signal)
}
