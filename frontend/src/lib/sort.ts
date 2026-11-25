import type { Category, Device } from '@/api/types'
import { STATUS_ORDER } from '@/lib/status'

export type SortKey = 'name' | 'ip' | 'category' | 'status'
export type SortDirection = 'asc' | 'desc'

const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

export function compareText(a: string, b: string): number {
  return collator.compare(a, b)
}

function ipv4Value(ip: string): number | null {
  const parts = ip.split('.')
  if (parts.length !== 4 || !parts.every((part) => /^\d{1,3}$/.test(part))) return null
  return parts.reduce((total, part) => total * 256 + Number(part), 0)
}

function ipv6Value(ip: string): bigint | null {
  if (!ip.includes(':')) return null
  let text = ip
  // An embedded IPv4 tail (::ffff:192.168.1.1) becomes two hex groups.
  const tail = /(\d+\.\d+\.\d+\.\d+)$/.exec(text)
  if (tail?.[1] !== undefined) {
    const value = ipv4Value(tail[1])
    if (value === null) return null
    text = `${text.slice(0, -tail[1].length)}${(value >>> 16).toString(16)}:${(value & 0xffff).toString(16)}`
  }
  const halves = text.split('::')
  if (halves.length > 2) return null
  const split = (half: string) => (half === '' ? [] : half.split(':'))
  const left = split(halves[0] ?? '')
  const right = halves.length === 2 ? split(halves[1] ?? '') : []
  const missing = 8 - left.length - right.length
  // Without "::" there must be exactly 8 groups; "::" stands for at least one zero group.
  if (halves.length === 1 ? missing !== 0 : missing < 1) return null
  const groups = [...left, ...Array<string>(halves.length === 2 ? missing : 0).fill('0'), ...right]
  let value = 0n
  for (const group of groups) {
    if (!/^[0-9a-fA-F]{1,4}$/.test(group)) return null
    value = (value << 16n) + BigInt(parseInt(group, 16))
  }
  return value
}

/** Numeric IP order: IPv4 before IPv6, each by value. Unparsable text sorts after both. */
export function compareIp(a: string, b: string): number {
  const a4 = ipv4Value(a)
  const b4 = ipv4Value(b)
  if (a4 !== null || b4 !== null) {
    if (a4 === null) return 1
    if (b4 === null) return -1
    return a4 - b4
  }
  const a6 = ipv6Value(a)
  const b6 = ipv6Value(b)
  if (a6 !== null || b6 !== null) {
    if (a6 === null) return 1
    if (b6 === null) return -1
    return a6 < b6 ? -1 : a6 > b6 ? 1 : 0
  }
  return compareText(a, b)
}

/**
 * Sorted copy. Devices without the sorted value (no IP, no category) always come last, in
 * either direction; ties are broken by name.
 */
export function sortDevices(
  devices: Device[],
  key: SortKey,
  direction: SortDirection,
  categories: Map<string, Category>,
): Device[] {
  const sign = direction === 'asc' ? 1 : -1
  if (key === 'status') {
    // Ascending: what needs attention first (down, no recent check, waiting, up, not checked).
    return [...devices].sort(
      (a, b) =>
        sign * (STATUS_ORDER[a.status] - STATUS_ORDER[b.status]) || compareText(a.name, b.name),
    )
  }
  const value = (device: Device): string | null => {
    if (key === 'ip') return device.ip_address
    if (key === 'category')
      return device.category_id === null ? null : (categories.get(device.category_id)?.name ?? null)
    return device.name
  }
  const compare = key === 'ip' ? compareIp : compareText
  return [...devices].sort((a, b) => {
    const va = value(a)
    const vb = value(b)
    if (va === null || vb === null) {
      if (va !== vb) return va === null ? 1 : -1
    } else {
      const result = compare(va, vb)
      if (result !== 0) return sign * result
    }
    return compareText(a.name, b.name)
  })
}
