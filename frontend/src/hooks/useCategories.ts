import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import { createCategory, deleteCategory, listCategories, updateCategory } from '@/api/categories'
import type { CategoryUpdate } from '@/api/types'
import { queryKeys } from '@/hooks/queryClient'

export function useCategories() {
  return useQuery({
    queryKey: queryKeys.categories,
    queryFn: ({ signal }) => listCategories(signal),
  })
}

/** The dashboard lists categories too (M7). */
function refreshCategories(client: QueryClient): Promise<unknown> {
  return Promise.all([
    client.invalidateQueries({ queryKey: queryKeys.categories }),
    client.invalidateQueries({ queryKey: queryKeys.dashboard }),
  ])
}

export function useCreateCategory() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: createCategory,
    onSuccess: () => refreshCategories(client),
  })
}

export function useUpdateCategory() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: CategoryUpdate }) => updateCategory(id, body),
    onSuccess: () => refreshCategories(client),
  })
}

export function useDeleteCategory() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: deleteCategory,
    // Its devices now have no category.
    onSuccess: () =>
      Promise.all([
        refreshCategories(client),
        client.invalidateQueries({ queryKey: queryKeys.devices }),
      ]),
  })
}
