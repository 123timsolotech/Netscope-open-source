import { api } from '@/api/client'
import type { Category, CategoryCreate, CategoryUpdate } from '@/api/types'

export function listCategories(signal?: AbortSignal): Promise<Category[]> {
  return api.get<Category[]>('/categories', signal)
}

export function createCategory(body: CategoryCreate): Promise<Category> {
  return api.post<Category>('/categories', body)
}

export function updateCategory(id: string, body: CategoryUpdate): Promise<Category> {
  return api.patch<Category>(`/categories/${encodeURIComponent(id)}`, body)
}

export function deleteCategory(id: string): Promise<undefined> {
  return api.delete(`/categories/${encodeURIComponent(id)}`)
}
