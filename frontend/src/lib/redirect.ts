/** The page after logging in and at `/`: the Dashboard (owner decision, M7). */
export const DEFAULT_PATH = '/dashboard'

/** Pages a login must never return to (they would bounce straight back). */
const AUTH_PAGES = ['/login', '/setup']

function hasControlCharacter(value: string): boolean {
  for (const char of value) {
    const code = char.charCodeAt(0)
    if (code < 0x20 || code === 0x7f) return true
  }
  return false
}

/**
 * The `?next=` target after logging in, if it is a page inside NetScope; otherwise
 * the Dashboard. Only same-origin paths pass: they start with a single "/", and there is no
 * "//" (another host) before or after resolving dot segments, no "\" (browsers read it as
 * "/"), scheme or control character (URL parsing drops tabs and line breaks, so
 * "/\t/evil.example" would become "//evil.example").
 */
export function safeNextPath(
  next: string | null | undefined,
  origin = window.location.origin,
): string {
  if (!next?.startsWith('/') || next.startsWith('//')) return DEFAULT_PATH
  if (next.includes('\\') || hasControlCharacter(next)) return DEFAULT_PATH
  let url: URL
  try {
    url = new URL(next, origin)
  } catch {
    return DEFAULT_PATH
  }
  if (url.origin !== origin) return DEFAULT_PATH
  // Dot segments collapse only while parsing: "/.//evil.example", "/x/..//evil.example" and
  // "/%2e//evil.example" all become "//evil.example", so check the parsed path as well.
  if (url.pathname.startsWith('//')) return DEFAULT_PATH
  if (AUTH_PAGES.some((page) => url.pathname === page || url.pathname.startsWith(`${page}/`))) {
    return DEFAULT_PATH
  }
  return `${url.pathname}${url.search}${url.hash}`
}

/** `/login?next=…` for the page the user wanted, without `next` for the default page. */
export function loginPathFor(pathWithSearch: string): string {
  if (pathWithSearch === '/' || pathWithSearch === DEFAULT_PATH) return '/login'
  return `/login?${new URLSearchParams({ next: pathWithSearch }).toString()}`
}

/** "Back" targets of the device form besides the device list (with its search and filters). */
const FORM_RETURN_LABELS: Record<string, string> = {
  '/topology': 'Topology',
  '/dashboard': 'Dashboard',
}

/**
 * Where the device form's "back" and a finished save go. Location state can hold anything,
 * so only the device list (any `?` search), the map and the dashboard pass; else `/devices`.
 */
export function formReturnTarget(returnTo: unknown): string {
  if (typeof returnTo !== 'string') return '/devices'
  return /^\/devices(\?|$)/.test(returnTo) || Object.hasOwn(FORM_RETURN_LABELS, returnTo)
    ? returnTo
    : '/devices'
}

/** The "back" link's text for a target from `formReturnTarget`. */
export function formReturnLabel(returnTo: string): string {
  // Own keys only: "constructor" would find Object's (decision M4.19).
  return Object.hasOwn(FORM_RETURN_LABELS, returnTo)
    ? (FORM_RETURN_LABELS[returnTo] ?? 'Devices')
    : 'Devices'
}
