import type { Category, Device } from '@/api/types'

/** Lower case, compatibility-normalized ("ﬁ" -> "fi", full-width digits -> digits). */
export function normalizeText(value: string): string {
  return value.normalize('NFKC').toLocaleLowerCase()
}

const MAC_SEPARATORS = /[:.-]/g
const HEX = /^[0-9a-f]+$/

/** The words of a search; every one must match somewhere in a device. */
export function searchTerms(query: string): string[] {
  return normalizeText(query).split(/\s+/).filter(Boolean)
}

function haystack(device: Device, category: Category | undefined): string[] {
  const fields: (string | null | undefined)[] = [
    device.name,
    device.hostname,
    device.ip_address,
    device.mac_address,
    device.vendor,
    device.role,
    device.location,
    device.description,
    category?.name,
  ]
  for (const service of device.services) {
    fields.push(
      service.name,
      service.note,
      String(service.port),
      `${String(service.port)}/${service.protocol}`,
    )
  }
  return fields.filter((field): field is string => Boolean(field)).map(normalizeText)
}

/**
 * Search in the browser (decision M3.15): name, hostname, IP, MAC (with or without
 * separators), vendor, role, location, description, category name and every service's name,
 * note and port. Case does not matter; every word must match.
 */
export function deviceMatches(
  device: Device,
  terms: string[],
  category: Category | undefined,
): boolean {
  if (terms.length === 0) return true
  const fields = haystack(device, category)
  const macDigits = device.mac_address?.replace(MAC_SEPARATORS, '').toLowerCase() ?? ''
  return terms.every((term) => {
    if (fields.some((field) => field.includes(term))) return true
    const digits = term.replace(MAC_SEPARATORS, '')
    return macDigits !== '' && digits.length >= 2 && HEX.test(digits) && macDigits.includes(digits)
  })
}

/** The category filter: a category id, "none" for devices without one, or null for all. */
export function categoryMatches(device: Device, filter: string | null): boolean {
  if (filter === null) return true
  if (filter === 'none') return device.category_id === null
  return device.category_id === filter
}
