import { api } from '@/api/client'
import type { About } from '@/api/types'

/** NetScope's version (M8: shown on the Settings pages, never in the public health check). */
export function getAbout(signal?: AbortSignal): Promise<About> {
  return api.get<About>('/about', signal)
}
