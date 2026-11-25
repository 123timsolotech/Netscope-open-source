import type { Device, DeviceStatus } from '@/api/types'

/**
 * Words for a device's status (owner decision, M6). The backend decides the status (`off`,
 * `waiting`, `up`, `down`, `stale`), so the list, the map and the dashboard agree; this only
 * puts it into words. Status never relies on color alone: every place shows these words, or
 * gives them to screen readers.
 */
export const STATUS_LABELS: Record<DeviceStatus, string> = {
  up: 'Up',
  down: 'Down',
  waiting: 'Waiting for check',
  stale: 'No recent check',
  off: 'Not checked',
}

/** "<1 ms", "3 ms", "1.2 s". */
export function formatLatency(ms: number): string {
  if (ms < 1) return '<1 ms'
  if (ms < 1000) return `${String(Math.round(ms))} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

/** The label plus the latency when up: "Up · 3 ms" (`separator` ", " for screen readers). */
export function statusText(device: Device, separator = ' · '): string {
  const label = STATUS_LABELS[device.status]
  if (device.status === 'up' && device.last_latency_ms !== null) {
    return `${label}${separator}${formatLatency(device.last_latency_ms)}`
  }
  return label
}

/** Local time of an API timestamp: only the time if it is today, else date and time. */
export function formatLocalTime(iso: string | null, now: Date = new Date()): string | null {
  if (iso === null) return null
  const time = new Date(iso)
  if (Number.isNaN(time.getTime())) return null
  const sameDay = time.toDateString() === now.toDateString()
  return sameDay
    ? time.toLocaleTimeString()
    : time.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'medium' })
}

/** Local time of the last check, or null if there was none. */
export function formatCheckedAt(device: Device, now: Date = new Date()): string | null {
  return formatLocalTime(device.last_checked_at, now)
}

/** Ends `text` with a period unless it already ends a sentence (some reasons do). */
function sentence(text: string): string {
  return /[.!?…]$/.test(text) ? text : `${text}.`
}

/** "Last check failed: …" for a status that is not down (the reason belongs to one check). */
export function failedCheckText(device: Device): string | null {
  const error = device.last_check_error
  if (error === null || device.status === 'off') return null
  return device.status === 'down' ? error : `Last check failed: ${error}`
}

/**
 * Everything about the status, for tooltips and screen readers:
 * "Down: Connection refused on port 22. Last check 18:42:10."
 */
export function statusDescription(device: Device, now?: Date): string {
  if (device.status === 'off') return sentence(STATUS_LABELS.off)
  const parts = [statusText(device)]
  const failed = failedCheckText(device)
  if (failed !== null) {
    if (device.status === 'down') parts[0] = `${parts[0]}: ${failed}`
    else parts.push(failed)
  }
  const checked = formatCheckedAt(device, now)
  if (checked !== null) parts.push(`Last check ${checked}`)
  return parts.map(sentence).join(' ')
}

/** List order when sorting by status: what needs attention first. */
export const STATUS_ORDER: Record<DeviceStatus, number> = {
  down: 0,
  stale: 1,
  waiting: 2,
  up: 3,
  off: 4,
}
