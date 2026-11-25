import type { Dashboard, DashboardCategory, DeviceStatus, StatusCounts } from '@/api/types'
import { STATUS_ORDER as STATUS_RANK } from '@/lib/status'

/**
 * The dashboard's logic (M7). The numbers come from the backend (`GET /api/dashboard`); this
 * only arranges them and puts them into words.
 */

/** The order of the Status card: the device list's status sort (what needs attention first,
 * "Not checked" last). */
export const STATUS_ORDER = (Object.keys(STATUS_RANK) as DeviceStatus[]).sort(
  (a, b) => STATUS_RANK[a] - STATUS_RANK[b],
)

const STATUS_WORDS: Record<Exclude<DeviceStatus, 'off'>, string> = {
  up: 'up',
  down: 'down',
  stale: 'no recent check',
  waiting: 'waiting for check',
}

export function devicesText(count: number): string {
  return `${String(count)} ${count === 1 ? 'device' : 'devices'}`
}

function countText(count: number, one: string, many: string): string {
  return `${String(count)} ${count === 1 ? one : many}`
}

/** "15 devices · 15 links · 42 services" (owner decision, M8). */
export function totalsText(
  dashboard: Pick<Dashboard, 'device_count' | 'link_count' | 'service_count'>,
): string {
  return [
    devicesText(dashboard.device_count),
    countText(dashboard.link_count, 'link', 'links'),
    countText(dashboard.service_count, 'service', 'services'),
  ].join(' · ')
}

/** "45 seconds", "3 minutes", "5 hours": seconds below 120 s, minutes below 120 minutes,
 * else hours; whole numbers, rounded down. */
export function quietDuration(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds))
  if (whole < 120) return countText(whole, 'second', 'seconds')
  if (whole < 120 * 60) return countText(Math.floor(whole / 60), 'minute', 'minutes')
  return countText(Math.floor(whole / 3600), 'hour', 'hours')
}

/** The warning when the status monitor looks stuck (owner decision, M8). */
export function monitorQuietText(seconds: number): string {
  return `No status check has finished for ${quietDuration(seconds)}. Is NetScope's monitor running? See the log.`
}

/** Devices whose check is on (every status but "Not checked"). */
export function checkedCount(counts: StatusCounts): number {
  return counts.up + counts.down + counts.waiting + counts.stale
}

/**
 * "8 of 15 devices checked: 6 up, 1 down" (owner decision, M7). Up and down are always named;
 * "no recent check" and "waiting for check" only when some device has them.
 */
export function summaryText(dashboard: Pick<Dashboard, 'device_count' | 'status_counts'>): string {
  const total = dashboard.device_count
  const counts = dashboard.status_counts
  const checked = checkedCount(counts)
  if (checked === 0) return `${devicesText(total)}, none checked`
  const parts = [`${String(counts.up)} up`, `${String(counts.down)} down`]
  for (const status of ['stale', 'waiting'] as const) {
    if (counts[status] > 0) parts.push(`${String(counts[status])} ${STATUS_WORDS[status]}`)
  }
  return `${String(checked)} of ${devicesText(total)} checked: ${parts.join(', ')}`
}

/** One row of "Devices by category": a category, or the devices without one (`category`
 * null). */
export interface CategoryRow {
  key: string
  category: DashboardCategory | null
  count: number
  /** The device list filtered by this row. */
  to: string
}

/**
 * Categories with devices, most first (the backend's order), then "No category" when some
 * device has none (owner decision, M7). Empty categories are only counted.
 */
export function categoryRows(dashboard: Pick<Dashboard, 'categories' | 'uncategorized_count'>): {
  rows: CategoryRow[]
  emptyCount: number
} {
  const rows: CategoryRow[] = dashboard.categories
    .filter((category) => category.device_count > 0)
    .map((category) => ({
      key: category.id,
      category,
      count: category.device_count,
      to: `/devices?category=${encodeURIComponent(category.id)}`,
    }))
  if (dashboard.uncategorized_count > 0) {
    rows.push({
      key: 'none',
      category: null,
      count: dashboard.uncategorized_count,
      to: '/devices?category=none',
    })
  }
  const emptyCount = dashboard.categories.filter((category) => category.device_count === 0).length
  return { rows, emptyCount }
}

/** A bar's width in percent of the largest row (at least a sliver, so 1 of 200 shows). */
export function barPercent(count: number, largest: number): number {
  if (largest <= 0 || count <= 0) return 0
  return Math.max(2, Math.round((count / largest) * 100))
}

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 365 * 24 * 3600],
  ['month', 30 * 24 * 3600],
  ['week', 7 * 24 * 3600],
  ['day', 24 * 3600],
  ['hour', 3600],
  ['minute', 60],
]

// "1 day ago", not "yesterday": the buckets count elapsed time, not calendar days (47 h
// would read "yesterday"; found in the review).
const relative = new Intl.RelativeTimeFormat('en', { numeric: 'always' })

/**
 * "just now", "5 minutes ago", "1 day ago", "3 weeks ago". English like the rest of the
 * interface; the exact local time goes into the tooltip. A time in the future (the server's
 * clock ahead of this one) reads "just now".
 */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const time = new Date(iso).getTime()
  if (Number.isNaN(time)) return ''
  const seconds = Math.round((now.getTime() - time) / 1000)
  if (seconds < 60) return 'just now'
  for (const [unit, size] of UNITS) {
    if (seconds >= size) return relative.format(-Math.floor(seconds / size), unit)
  }
  return 'just now'
}

/** Where the quick search goes: the device list with the search in its URL (`?q=`). */
export function searchPath(query: string): string {
  const trimmed = query.trim()
  return trimmed === '' ? '/devices' : `/devices?${new URLSearchParams({ q: trimmed }).toString()}`
}
