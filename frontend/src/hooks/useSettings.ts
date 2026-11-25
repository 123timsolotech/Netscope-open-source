import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getSettings, updateSettings } from '@/api/settings'
import { queryKeys } from '@/hooks/queryClient'

export function useSettings() {
  return useQuery({
    queryKey: queryKeys.settings,
    queryFn: ({ signal }) => getSettings(signal),
  })
}

export function useUpdateSettings() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: updateSettings,
    onSuccess: (saved) => {
      client.setQueryData(queryKeys.settings, saved)
      // "No recent check" depends on the interval: the backend recomputes each status.
      return Promise.all([
        client.invalidateQueries({ queryKey: queryKeys.devices }),
        client.invalidateQueries({ queryKey: queryKeys.dashboard }),
      ])
    },
  })
}
