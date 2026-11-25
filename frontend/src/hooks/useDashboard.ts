import { useQuery } from '@tanstack/react-query'

import { getDashboard } from '@/api/dashboard'
import { POLL_INTERVAL_MS, queryKeys, WAITING_POLL_INTERVAL_MS } from '@/hooks/queryClient'

/**
 * The dashboard's numbers, loaded again like the device list (M6): every 30 s while the tab
 * is visible, every 5 s while a device waits for its first result.
 */
export function useDashboard() {
  return useQuery({
    queryKey: queryKeys.dashboard,
    queryFn: ({ signal }) => getDashboard(signal),
    refetchInterval: (query) =>
      query.state.data?.first_results_pending ? WAITING_POLL_INTERVAL_MS : POLL_INTERVAL_MS,
  })
}
