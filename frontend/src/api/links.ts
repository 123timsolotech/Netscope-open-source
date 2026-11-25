import { api } from '@/api/client'
import type { Link, LinkCreate, LinkUpdate } from '@/api/types'

/** Links have no direction: `device_a_id` is always the smaller id. */
export function listLinks(signal?: AbortSignal): Promise<Link[]> {
  return api.get<Link[]>('/links', signal)
}

/** Self-links and duplicates are a 422 on `device_b_id`. */
export function createLink(body: LinkCreate): Promise<Link> {
  return api.post<Link>('/links', body)
}

/** Type and label only: the two devices cannot change (delete and create instead). */
export function updateLink(id: string, body: LinkUpdate): Promise<Link> {
  return api.patch<Link>(`/links/${encodeURIComponent(id)}`, body)
}

export function deleteLink(id: string): Promise<undefined> {
  return api.delete(`/links/${encodeURIComponent(id)}`)
}
