import { isApiError } from '@/api/client'
import type { ImportCounts, ImportResult, Issue } from '@/api/types'

/**
 * Export and import (M8): reading the chosen file, the light size check, the problems of a
 * refused file in words, and what an import will do (or did) in plain sentences. The backend
 * checks the file; this only puts its answers into words.
 */

/** The backend's import limit (owner decision, M8). Checked here first, lightly: the backend
 * decides (413). */
export const MAX_IMPORT_BYTES = 10 * 1024 * 1024

export const TOO_LARGE_MESSAGE = 'The file is too large: NetScope imports at most 10 MiB.'
export const NOT_UTF8_MESSAGE =
  'The file is not UTF-8 text. Export it from NetScope again, or save it as UTF-8.'
export const UNREADABLE_MESSAGE = 'Could not read the file. Choose it again.'
/** Shape errors stop the backend before its rules between entries run (two rounds). */
export const TWO_ROUNDS_HINT =
  'Some problems show only once these are fixed: check the file again after fixing them.'

/** How many problems the page lists; the rest are counted. */
export const MAX_PROBLEMS_SHOWN = 50

export function isTooLarge(bytes: number): boolean {
  return bytes > MAX_IMPORT_BYTES
}

/**
 * "512 bytes", "3.4 KiB", "12 KiB", "2.5 MiB" (binary units, like the 10 MiB limit). One
 * decimal below 10, whole numbers above, always rounded down: a size never reads larger than
 * it is (10 MiB and 1 byte reads "10 MiB", so the page says "more than 10 MiB" for files
 * above the limit).
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${String(bytes)} ${bytes === 1 ? 'byte' : 'bytes'}`
  const [value, unit] = bytes < 1024 * 1024 ? [bytes / 1024, 'KiB'] : [bytes / 1024 ** 2, 'MiB']
  const shown = value < 10 ? (Math.floor(value * 10) / 10).toFixed(1) : String(Math.floor(value))
  return `${shown} ${unit}`
}

/** The size shown next to the chosen file. */
export function chosenFileSize(bytes: number): string {
  return isTooLarge(bytes) ? 'more than 10 MiB' : formatFileSize(bytes)
}

/** The file could not be read, or is not UTF-8: nothing was sent. */
export class FileProblemError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'FileProblemError'
  }
}

/**
 * The chosen file's text, exactly as its bytes say (a leading UTF-8 byte order mark is
 * dropped). Bytes that are not UTF-8 are refused instead of being replaced with "�", which
 * would change names silently (found in the M8 review: a Latin-1 "Café").
 */
export async function readImportFile(file: Blob): Promise<string> {
  let bytes: Uint8Array
  try {
    bytes = new Uint8Array(await file.arrayBuffer())
  } catch {
    throw new FileProblemError(UNREADABLE_MESSAGE)
  }
  try {
    // ignoreBOM false (the default): a BOM is dropped, not passed on.
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } catch {
    throw new FileProblemError(NOT_UTF8_MESSAGE)
  }
}

/**
 * The file as JSON, parsed in the browser only to name entries in the list of problems (the
 * file is sent as its text, unchanged). Undefined when it is not JSON.
 */
export function parseForDisplay(text: string): unknown {
  try {
    return JSON.parse(text) as unknown
  } catch {
    return undefined
  }
}

/** A file the backend refused (422), with what the browser could parse of it. */
export class RefusedFileError extends Error {
  readonly issues: Issue[]
  readonly document: unknown

  constructor(issues: Issue[], document: unknown) {
    super('This file cannot be imported.')
    this.name = 'RefusedFileError'
    this.issues = issues
    this.document = document
  }
}

/** The lists of an export file, by the word for one of their items. A Map, so names such as
 * "constructor" find nothing. */
const ITEM_WORDS = new Map([
  ['categories', 'Category'],
  ['devices', 'Device'],
  ['links', 'Link'],
  ['services', 'Service'],
])

/** Parts of field names written in capitals. */
const UPPER_WORDS = new Set(['ip', 'mac', 'id', 'tls', 'url', 'a', 'b'])

/** `check_port` -> "check port", `ip_address` -> "IP address", `device_a_id` -> "device A ID". */
export function fieldWords(name: string): string {
  return name
    .split('_')
    .filter((word) => word !== '')
    .map((word) => (UPPER_WORDS.has(word.toLowerCase()) ? word.toUpperCase() : word))
    .join(' ')
}

/** `value[key]` for JSON data: an array's item or an object's own field, else undefined. */
function member(value: unknown, key: string | number): unknown {
  if (Array.isArray(value)) return typeof key === 'number' ? (value[key] as unknown) : undefined
  if (typeof value !== 'object' || value === null || typeof key !== 'string') return undefined
  return Object.hasOwn(value, key) ? (value as Record<string, unknown>)[key] : undefined
}

const NAME_LENGTH = 40
const graphemes = new Intl.Segmenter('en', { granularity: 'grapheme' })

/** A name for the place of a problem: spaces collapsed, cut to 40 characters (whole emoji
 * and accented letters, not halves of them). */
function shortName(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const text = value.trim().replace(/\s+/g, ' ')
  if (text === '') return null
  const characters = Array.from(graphemes.segment(text), (part) => part.segment)
  if (characters.length <= NAME_LENGTH) return text
  return `${characters.slice(0, NAME_LENGTH - 1).join('')}…`
}

/** A device's, category's or service's name; a link's two device names. */
function entryName(list: string, entry: unknown, document: unknown): string | null {
  if (list !== 'links') return shortName(member(entry, 'name'))
  const devices = member(document, 'devices')
  if (!Array.isArray(devices)) return null
  const nameOf = (id: unknown) =>
    typeof id === 'string'
      ? shortName(member(devices.find((device) => member(device, 'id') === id) as unknown, 'name'))
      : null
  const a = nameOf(member(entry, 'device_a_id'))
  const b = nameOf(member(entry, 'device_b_id'))
  return a !== null && b !== null ? `${a} – ${b}` : null
}

/**
 * Where in the file a problem is, from its `loc`: `["body", "devices", 3, "services", 1,
 * "port"]` -> "Device 4 (nas), Service 2 (SSH), port" (counted from 1). The names come from
 * `document`, the file as parsed in the browser, when it has them. "body" is left out; an
 * empty string means the whole file.
 */
export function problemPlace(loc: readonly (string | number)[], document?: unknown): string {
  const parts = loc[0] === 'body' ? loc.slice(1) : [...loc]
  const words: string[] = []
  let node = document
  for (let index = 0; index < parts.length; index++) {
    const part = parts[index]
    const next = parts[index + 1]
    if (typeof part === 'string' && typeof next === 'number') {
      const entry = member(member(node, part), next)
      const word = ITEM_WORDS.get(part)
      const name = word === undefined ? null : entryName(part, entry, document)
      const label = `${word ?? fieldWords(part)} ${String(next + 1)}`
      words.push(name === null ? label : `${label} (${name})`)
      node = entry
      index++
    } else if (typeof part === 'number') {
      words.push(`item ${String(part + 1)}`)
      node = member(node, part)
    } else {
      words.push(part === 'settings' ? 'Settings' : fieldWords(part))
      node = member(node, part)
    }
  }
  const place = words.join(', ')
  return place.charAt(0).toUpperCase() + place.slice(1)
}

/** One problem as a line: "Device 4 (nas), Service 2 (SSH), port: Input should be …". */
export function problemText(issue: Issue, document?: unknown): string {
  const place = problemPlace(issue.loc, document)
  return place === '' ? issue.msg : `${place}: ${issue.msg}`
}

/**
 * The character a JSON syntax error is at, counted from 1, or null when `issues` is not one.
 * FastAPI answers `{"type": "json_invalid", "loc": ["body", <offset from 0>]}`.
 */
export function jsonErrorPosition(issues: readonly Issue[]): number | null {
  if (issues.length !== 1) return null
  const [where, offset] = issues[0].loc
  if (issues[0].loc.length !== 2 || where !== 'body' || typeof offset !== 'number') return null
  return offset + 1
}

/** Every problem of a refused file as a line, at most `limit`, then how many more. */
export function problemLines(
  issues: readonly Issue[],
  document?: unknown,
  limit = MAX_PROBLEMS_SHOWN,
): string[] {
  const position = jsonErrorPosition(issues)
  if (position !== null) {
    return [`The file is not valid JSON (near character ${String(position)}).`]
  }
  const lines = issues.slice(0, limit).map((issue) => problemText(issue, document))
  const more = issues.length - limit
  if (more > 0) lines.push(`…and ${String(more)} more ${more === 1 ? 'problem' : 'problems'}.`)
  return lines
}

/** "a", "a and b", "a, b and c". */
function andList(items: readonly string[]): string {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} and ${items.at(-1) ?? ''}`
}

function count(n: number, one: string, many: string): string {
  return `${String(n)} ${n === 1 ? one : many}`
}

type Kind = 'devices' | 'categories' | 'links'
const KINDS: { kind: Kind; one: string; many: string; title: string }[] = [
  { kind: 'devices', one: 'device', many: 'devices', title: 'Devices' },
  { kind: 'categories', one: 'category', many: 'categories', title: 'Categories' },
  { kind: 'links', one: 'link', many: 'links', title: 'Links' },
]

type Counts = Pick<ImportResult, Kind>

/** "20 devices, 12 categories and 15 links", leaving out kinds with none ("12 categories");
 * null when all three are 0. */
export function countsText(result: Counts, field: 'added' | 'deleted'): string | null {
  const parts = KINDS.filter(({ kind }) => result[kind][field] > 0).map(({ kind, one, many }) =>
    count(result[kind][field], one, many),
  )
  return parts.length === 0 ? null : andList(parts)
}

function mergeLine(title: string, counts: ImportCounts): string {
  const parts = (['added', 'updated', 'unchanged'] as const)
    .filter((field) => counts[field] > 0)
    .map((field) => `${String(counts[field])} ${field}`)
  return parts.length === 0 ? `${title}: none in the file.` : `${title}: ${parts.join(', ')}.`
}

/** "a, b and c", or "a, b, c and 12 more" when the backend listed only some of `total`. */
function namesText(names: readonly string[], total: number): string {
  const more = total - names.length
  return more > 0 ? `${names.join(', ')} and ${String(more)} more` : andList(names)
}

/** The devices added and updated, by name (the backend lists at most 20 of each). */
function nameLines(result: ImportResult): string[] {
  const planned = result.dry_run
  const lines: string[] = []
  if (result.added_device_names.length > 0) {
    const names = namesText(result.added_device_names, result.devices.added)
    lines.push(planned ? `To add: ${names}.` : `Added: ${names}.`)
  }
  if (result.updated_device_names.length > 0) {
    const names = namesText(result.updated_device_names, result.devices.updated)
    lines.push(planned ? `To update: ${names}.` : `Updated: ${names}.`)
  }
  return lines
}

/** Devices whose status check is on after the import: NetScope checks them at once. Null
 * for none. */
export function checksOnText(result: Pick<ImportResult, 'checks_on' | 'dry_run'>): string | null {
  const n = result.checks_on
  if (n <= 0) return null
  const devices =
    n === 1 ? '1 device has its status check on' : `${String(n)} devices have status checks on`
  const them = n === 1 ? 'it' : 'them'
  return result.dry_run
    ? `${devices}: NetScope starts checking ${them} right after the import.`
    : `${devices}: NetScope starts checking ${them} now.`
}

/**
 * What an import will do (a dry run) or did, in sentences (owner decision, M8: the page shows
 * what will be added, changed and deleted before you confirm).
 */
export function importSummary(result: ImportResult): string[] {
  const planned = result.dry_run
  const checks = checksOnText(result)
  const extra = [...nameLines(result), ...(checks === null ? [] : [checks])]
  if (result.mode === 'merge') {
    return [
      ...KINDS.map(({ kind, title }) => mergeLine(title, result[kind])),
      ...extra,
      planned ? 'Settings stay as they are.' : 'Settings stayed as they were.',
    ]
  }
  const deleted = countsText(result, 'deleted')
  const added = countsText(result, 'added')
  const lines = planned
    ? [
        deleted === null ? 'Deletes nothing.' : `Deletes ${deleted}.`,
        added === null ? 'Adds nothing from the file.' : `Adds ${added} from the file.`,
      ]
    : [
        deleted === null ? 'Deleted nothing.' : `Deleted ${deleted}.`,
        added === null ? 'Added nothing from the file.' : `Added ${added} from the file.`,
      ]
  const settings = planned
    ? result.settings_changed
      ? 'Your status-check settings change.'
      : 'Your status-check settings stay as they are.'
    : result.settings_changed
      ? 'Your status-check settings changed.'
      : 'Your status-check settings stayed as they were.'
  return [...lines, ...extra, settings]
}

/** What Replace all deletes, for the confirmation (owner decision, M8). */
export function replaceWarning(check: ImportResult): string {
  const deleted = countsText(check, 'deleted')
  const sentences = [
    deleted === null
      ? 'NetScope has no devices, categories or links yet, so nothing is deleted.'
      : `This deletes ${deleted}${check.devices.deleted > 0 ? ", with the devices' status history" : ''}, and then adds what is in the file.`,
  ]
  const checks = checksOnText(check)
  if (checks !== null) sentences.push(checks)
  sentences.push('Your login stays, and NetScope saves a copy of the database first.')
  return sentences.join(' ')
}

/** Why a check or an import failed, for the page: a title and plain-text lines. */
export interface ImportProblem {
  title: string
  lines: string[]
  /** A line under the list. */
  hint?: string
  /** The file must be checked again (it was refused, NetScope's data changed, or the import
   * failed on NetScope's side). */
  checkAgain: boolean
  /** NetScope could not be reached at all: the confirmation stays open, to try again. */
  keepDialog: boolean
}

export const CANNOT_IMPORT = 'This file cannot be imported.'

/** Proxies (Vite, Tailscale Serve) answer these when NetScope is not running. */
const PROXY_STATUSES = new Set([502, 503, 504])

export function importProblem(error: unknown, action: 'check' | 'import'): ImportProblem {
  const refused = { title: CANNOT_IMPORT, checkAgain: true, keepDialog: false }
  if (error instanceof FileProblemError) return { ...refused, lines: [error.message] }
  if (error instanceof RefusedFileError) {
    return { ...refused, lines: problemLines(error.issues, error.document), hint: TWO_ROUNDS_HINT }
  }
  if (isApiError(error, 422)) {
    const lines = error.issues.length > 0 ? problemLines(error.issues) : [error.message]
    return { ...refused, lines, hint: TWO_ROUNDS_HINT }
  }
  if (isApiError(error, 413)) return { ...refused, lines: [TOO_LARGE_MESSAGE] }
  if (isApiError(error, 409)) {
    // "NetScope's data changed during the import. Check the file again." or "Another import
    // is running. …": either way the check is out of date.
    const again = /check the file again/i.test(error.message) ? [] : ['Check the file again.']
    return { ...refused, title: 'Could not import the file.', lines: [error.message, ...again] }
  }
  const title = action === 'check' ? 'Could not check the file.' : 'Could not import the file.'
  if (isApiError(error) && error.status >= 500) {
    // NetScope's own "busy" answer (a 503 with its message): nothing happened, try again.
    if (error.status === 503 && error.detail !== null) {
      return { title, lines: [error.detail], checkAgain: false, keepDialog: false }
    }
    const line =
      error.detail === null && PROXY_STATUSES.has(error.status)
        ? error.message // a proxy: NetScope is not running
        : `The ${action} failed on NetScope's side (error ${String(error.status)}). See NetScope's log.`
    return { title, lines: [line], checkAgain: true, keepDialog: false }
  }
  const message = error instanceof Error ? error.message : 'Something went wrong.'
  return { title, lines: [message], checkAgain: false, keepDialog: isApiError(error, 0) }
}
