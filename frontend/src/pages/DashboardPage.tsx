import { Plus } from 'lucide-react'
import { useMemo } from 'react'
import { Link } from 'react-router'

import type { DeviceFormLocationState } from '@/components/devices/DeviceForm'
import {
  CategoriesCard,
  DownCard,
  RecentCard,
  StatusCard,
} from '@/components/dashboard/DashboardCards'
import { QuickSearch } from '@/components/dashboard/QuickSearch'
import { Notice } from '@/components/Notice'
import { EmptyState, ErrorState, LoadingState, RefreshNotice } from '@/components/PageStates'
import { Button } from '@/components/ui/button'
import { useDashboard } from '@/hooks/useDashboard'
import { categoryRows, monitorQuietText, summaryText, totalsText } from '@/lib/dashboard'

const FORM_STATE: DeviceFormLocationState = { returnTo: '/dashboard' }

/**
 * The landing page (M7): how many devices, how many are up and down, which are down, counts
 * by category, recently edited, and a quick search. Every number comes from the backend.
 */
export function DashboardPage() {
  const dashboard = useDashboard()
  const data = dashboard.data
  const categories = useMemo(
    () => new Map((data?.categories ?? []).map((category) => [category.id, category])),
    [data?.categories],
  )

  if (dashboard.isPending) return <LoadingState />
  // An error page only when nothing was loaded: a failed poll keeps the page (RefreshNotice).
  if (data === undefined)
    return <ErrorState error={dashboard.error} onRetry={() => void dashboard.refetch()} />

  // "5 minutes ago" is counted from the last successful load, so it moves on with each poll.
  const now = new Date(dashboard.dataUpdatedAt)
  const { rows, emptyCount } = categoryRows(data)

  return (
    <div className="grid gap-6">
      <header>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        {data.device_count > 0 && (
          <>
            <p className="text-sm text-muted-foreground">{summaryText(data)}</p>
            <p className="text-sm text-muted-foreground">{totalsText(data)}</p>
          </>
        )}
      </header>

      {/* Not a live region: the number grows with every poll and would be read out each time.
          The status line below announces the problem once, when it starts. */}
      {data.monitor_quiet_seconds !== null && (
        <Notice tone="warning" live={false} title={monitorQuietText(data.monitor_quiet_seconds)} />
      )}
      <p role="status" className="sr-only">
        {data.monitor_quiet_seconds !== null ? 'Status checks seem to have stopped.' : ''}
      </p>

      {dashboard.isError && <RefreshNotice error={dashboard.error} />}

      {data.device_count === 0 ? (
        <EmptyState
          title="No devices yet"
          description="Add your router, switches, servers and everything else on your network. NetScope does not scan; you enter each device yourself."
          action={
            <Button asChild>
              <Link to="/devices/new" state={FORM_STATE}>
                <Plus aria-hidden="true" />
                Add your first device
              </Link>
            </Button>
          }
        />
      ) : (
        <>
          <QuickSearch />
          <div className="grid items-start gap-6 lg:grid-cols-2">
            <StatusCard counts={data.status_counts} />
            <DownCard
              down={data.down}
              counts={data.status_counts}
              categories={categories}
              now={now}
            />
            <CategoriesCard rows={rows} emptyCount={emptyCount} />
            <RecentCard recent={data.recently_edited} categories={categories} now={now} />
          </div>
        </>
      )}
    </div>
  )
}
