import { useQuery } from '@tanstack/react-query'

import { getAbout } from '@/api/about'
import { queryKeys } from '@/hooks/queryClient'

/** NetScope's version; it changes only with an update, which reloads the page anyway. */
export function useAbout() {
  return useQuery({
    queryKey: queryKeys.about,
    queryFn: ({ signal }) => getAbout(signal),
    staleTime: Infinity,
  })
}
