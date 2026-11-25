import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { isApiError } from '@/api/client'
import { createLink, deleteLink, listLinks, updateLink } from '@/api/links'
import type { LinkUpdate } from '@/api/types'
import { queryKeys } from '@/hooks/queryClient'

export function useLinks() {
  return useQuery({
    queryKey: queryKeys.links,
    queryFn: ({ signal }) => listLinks(signal),
  })
}

export function useCreateLink() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: createLink,
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.links }),
  })
}

export function useUpdateLink() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: LinkUpdate }) => updateLink(id, body),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.links }),
    // Deleted meanwhile (another tab): stop showing it.
    onError: (error) =>
      isApiError(error, 404) ? client.invalidateQueries({ queryKey: queryKeys.links }) : undefined,
  })
}

export function useDeleteLink() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: deleteLink,
    // Also after a 404: the link is gone either way, so the map should stop showing it.
    onSettled: () => client.invalidateQueries({ queryKey: queryKeys.links }),
  })
}
