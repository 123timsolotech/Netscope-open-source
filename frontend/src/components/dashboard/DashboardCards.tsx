import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type {
  DashboardCategory,
  DeviceStatus,
  DownDevice,
  RecentDevice,
  StatusCounts,
} from '@/api/types'
import { CategoryIcon } from '@/components/CategoryIcon'
import type { DeviceFormLocationState } from '@/components/devices/DeviceForm'
import { StatusDot } from '@/components/StatusDot'
import { safeColor } from '@/lib/colors'
import {
  barPercent,
  checkedCount,
  devicesText,
  STATUS_ORDER,
  timeAgo,
  type CategoryRow,
} from '@/lib/dashboard'
import { formatLocalTime, STATUS_LABELS } from '@/lib/status'
import { cn } from '@/lib/utils'

/** A device form opened from the dashboard returns to it (owner decision, M7). */
const FORM_STATE: DeviceFormLocationState = { returnTo: '/dashboard' }
/** The device list sorted by status, down first (owner decision, M7: no status filter). */
const BY_STATUS = '/devices?sort=status'
const LINK = 'rounded-sm hover:text-primary hover:underline'

function Card({
  title,
  children,
  className,
}: {
  title: string
  children: ReactNode
  className?: string
}) {
  const id = `dashboard-${title.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <section
      aria-labelledby={id}
      className={cn('grid content-start gap-4 rounded-xl border bg-card p-4 sm:p-5', className)}
    >
      <h2 id={id} className="font-medium">
        {title}
      </h2>
      {children}
    </section>
  )
}

function Muted({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>
}

/** Keeps the rows aligned where a status has no sign ("Not checked"). */
function Sign({ status }: { status: DeviceStatus }) {
  return status === 'off' ? (
    <span aria-hidden="true" className="size-4 shrink-0" />
  ) : (
    <StatusDot status={status} className="size-4" />
  )
}

function categoryOf(
  categories: ReadonlyMap<string, DashboardCategory>,
  id: string | null,
): DashboardCategory | undefined {
  return id === null ? undefined : categories.get(id)
}

/** The device's category icon, or an empty slot of the same size. */
function DeviceIcon({ category }: { category: DashboardCategory | undefined }) {
  if (!category) return <span aria-hidden="true" className="size-4 shrink-0" />
  return <CategoryIcon icon={category.icon} color={category.color} />
}

function DownIcon({ category }: { category: DashboardCategory | undefined }) {
  return category ? <CategoryIcon icon={category.icon} color={category.color} /> : null
}

export function StatusCard({ counts }: { counts: StatusCounts }) {
  return (
    <Card title="Status">
      <ul className="grid gap-1">
        {STATUS_ORDER.map((status) => {
          const count = counts[status]
          const content = (
            <>
              <Sign status={status} />
              <span className="flex-1">{STATUS_LABELS[status]}</span>
              <span className="font-medium tabular-nums">{count}</span>
            </>
          )
          return (
            <li key={status} data-status={status}>
              {count > 0 ? (
                <Link
                  to={BY_STATUS}
                  aria-label={`${STATUS_LABELS[status]}: ${devicesText(count)}`}
                  className="-mx-2 flex items-center gap-3 rounded-md px-2 py-1.5 text-sm hover:bg-accent"
                >
                  {content}
                </Link>
              ) : (
                <span className="-mx-2 flex items-center gap-3 px-2 py-1.5 text-sm text-muted-foreground">
                  {content}
                </span>
              )}
            </li>
          )
        })}
      </ul>
      {checkedCount(counts) === 0 && (
        <Muted>
          No device is checked yet. To watch one, open it and turn on its status check (under
          “Status check”).
        </Muted>
      )}
    </Card>
  )
}

export function DownCard({
  down,
  counts,
  categories,
  now,
}: {
  down: DownDevice[]
  counts: StatusCounts
  categories: ReadonlyMap<string, DashboardCategory>
  now: Date
}) {
  return (
    <Card title="Down now">
      {down.length === 0 ? (
        <Muted>{checkedCount(counts) === 0 ? 'No device is checked.' : 'No device is down.'}</Muted>
      ) : (
        <ul className="grid gap-3">
          {down.map((device) => {
            const checked = formatLocalTime(device.last_checked_at, now)
            return (
              <li key={device.id} className="flex min-w-0 gap-3">
                <StatusDot status="down" className="mt-0.5 size-4" />
                <div className="grid min-w-0 flex-1 gap-0.5">
                  <span className="flex min-w-0 items-center gap-2">
                    {/* No empty slot here: the down sign already leads the row. */}
                    <DownIcon category={categoryOf(categories, device.category_id)} />
                    <Link
                      to={`/devices/${device.id}`}
                      state={FORM_STATE}
                      dir="auto"
                      title={device.name}
                      className={cn(LINK, 'truncate font-medium')}
                    >
                      {device.name}
                    </Link>
                    <span className="sr-only">: {STATUS_LABELS.down}</span>
                  </span>
                  {device.last_check_error && (
                    <span className="text-sm break-words">{device.last_check_error}</span>
                  )}
                  {checked && (
                    <span className="text-xs text-muted-foreground">Last check {checked}</span>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

export function CategoriesCard({ rows, emptyCount }: { rows: CategoryRow[]; emptyCount: number }) {
  const largest = Math.max(0, ...rows.map((row) => row.count))
  return (
    <Card title="Devices by category">
      <ul className="grid gap-3">
        {rows.map((row) => (
          <li key={row.key}>
            <Link
              to={row.to}
              aria-label={`${row.category?.name ?? 'No category'}: ${devicesText(row.count)}`}
              className="group -mx-2 grid gap-1.5 rounded-md px-2 py-1 hover:bg-accent"
            >
              <span className="flex min-w-0 items-center gap-2 text-sm">
                {row.category ? (
                  <CategoryIcon icon={row.category.icon} color={row.category.color} />
                ) : (
                  <span aria-hidden="true" className="size-4 shrink-0" />
                )}
                <span
                  dir="auto"
                  title={row.category?.name ?? 'No category'}
                  className={cn(
                    'flex-1 truncate text-left',
                    !row.category && 'text-muted-foreground',
                  )}
                >
                  {row.category?.name ?? 'No category'}
                </span>
                <span className="font-medium tabular-nums">{row.count}</span>
              </span>
              <span
                aria-hidden="true"
                className="block h-1.5 overflow-hidden rounded-full bg-muted"
              >
                <span
                  className="block h-full rounded-full bg-muted-foreground"
                  style={{
                    width: `${String(barPercent(row.count, largest))}%`,
                    backgroundColor: row.category ? safeColor(row.category.color) : undefined,
                  }}
                />
              </span>
            </Link>
          </li>
        ))}
      </ul>
      {emptyCount > 0 && (
        <p className="text-sm text-muted-foreground">
          <Link to="/settings/categories" className={LINK}>
            {emptyCount === 1 ? '1 category has' : `${String(emptyCount)} categories have`} no
            devices
          </Link>
        </p>
      )}
    </Card>
  )
}

export function RecentCard({
  recent,
  categories,
  now,
}: {
  recent: RecentDevice[]
  categories: ReadonlyMap<string, DashboardCategory>
  now: Date
}) {
  return (
    <Card title="Recently edited">
      <ul className="grid gap-2">
        {recent.map((device) => {
          const exact = formatLocalTime(device.updated_at, now) ?? undefined
          return (
            <li key={device.id} className="flex min-w-0 items-center gap-2 text-sm">
              <DeviceIcon category={categoryOf(categories, device.category_id)} />
              <Link
                to={`/devices/${device.id}`}
                state={FORM_STATE}
                dir="auto"
                title={device.name}
                className={cn(LINK, 'min-w-0 flex-1 truncate text-left font-medium')}
              >
                {device.name}
              </Link>
              <span className="shrink-0 text-muted-foreground">
                {device.added ? 'Added' : 'Edited'}{' '}
                <time dateTime={device.updated_at} title={exact}>
                  {timeAgo(device.updated_at, now)}
                </time>
              </span>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
