/**
 * Typed client for the NetScope backend.
 * All fetch calls live in src/api. UI components never call fetch directly.
 */

import type { Issue } from '@/api/types'

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

/** An answer other than 2xx, or no answer at all (`status` 0). */
export class ApiError extends Error {
  readonly status: number
  /** 422 only: every problem, in the backend's list format (decision M3.1). */
  readonly issues: Issue[]
  /** 429 only: seconds from the `Retry-After` header. */
  readonly retryAfter: number | null
  /** NetScope's own message (`{"detail": "…"}`), if it sent one; null for a fallback (no
   * answer, or one from a proxy in front). */
  readonly detail: string | null

  constructor(
    status: number,
    message: string,
    options: { issues?: Issue[]; retryAfter?: number | null; detail?: string | null } = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.issues = options.issues ?? []
    this.retryAfter = options.retryAfter ?? null
    this.detail = options.detail ?? null
  }
}

export function isApiError(error: unknown, status?: number): error is ApiError {
  return error instanceof ApiError && (status === undefined || error.status === status)
}

const UNREACHABLE = 'Cannot reach NetScope. Check that it is running.'

const FALLBACK_MESSAGES: Record<number, string> = {
  400: 'NetScope refused the request.',
  401: 'Please log in.',
  403: 'NetScope refused the request.',
  404: 'Not found.',
  413: 'Request body too large.',
  415: 'NetScope refused the request.',
  422: 'Some fields need attention.',
  429: 'Too many attempts. Try again later.',
  // A proxy in front (Vite in development, Tailscale Serve) answers these when NetScope is down.
  502: UNREACHABLE,
  503: UNREACHABLE,
  504: UNREACHABLE,
}

function isIssue(value: unknown): value is Issue {
  if (typeof value !== 'object' || value === null) return false
  const item = value as Record<string, unknown>
  return (
    typeof item.msg === 'string' &&
    typeof item.type === 'string' &&
    Array.isArray(item.loc) &&
    item.loc.every((part) => typeof part === 'string' || typeof part === 'number')
  )
}

function parseRetryAfter(header: string | null): number | null {
  if (header === null || !/^\d+$/.test(header.trim())) return null
  return Number(header.trim())
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text()
  if (text === '') return undefined
  try {
    return JSON.parse(text) as unknown
  } catch {
    return undefined
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  const body = await readJson(response)
  const detail =
    typeof body === 'object' && body !== null ? (body as { detail?: unknown }).detail : undefined
  const fallback =
    FALLBACK_MESSAGES[response.status] ?? `NetScope answered with error ${String(response.status)}.`
  const retryAfter =
    response.status === 429 ? parseRetryAfter(response.headers.get('Retry-After')) : null

  if (Array.isArray(detail)) {
    const issues = detail.filter(isIssue)
    return new ApiError(response.status, fallback, { issues, retryAfter })
  }
  const own = typeof detail === 'string' && detail.trim() !== '' ? detail : null
  return new ApiError(response.status, own ?? fallback, { retryAfter, detail: own })
}

interface RequestOptions {
  /** Sent as JSON. POST, PUT and PATCH always send a JSON body (`{}` if none is given). */
  body?: unknown
  /**
   * Sent exactly as given instead of `body`, still as `application/json` (the import sends
   * the chosen file's text unchanged: the backend parses and checks it).
   */
  rawBody?: string
  signal?: AbortSignal
}

/**
 * Sends one request to `/api{path}` and returns the answer as it is, after turning a non-2xx
 * answer (or none at all) into an `ApiError`.
 *
 * Every POST, PUT and PATCH carries `Content-Type: application/json`, or the backend answers
 * 415 (security audit A.2). The session cookie goes along automatically (same origin).
 */
async function send(method: Method, path: string, options: RequestOptions): Promise<Response> {
  const headers = new Headers({ Accept: 'application/json' })
  let body: string | undefined
  if (method === 'POST' || method === 'PUT' || method === 'PATCH') {
    headers.set('Content-Type', 'application/json')
    body = options.rawBody ?? JSON.stringify(options.body ?? {})
  }

  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers,
      body,
      credentials: 'same-origin',
      signal: options.signal,
    })
  } catch (error) {
    if (options.signal?.aborted) throw error
    throw new ApiError(0, UNREACHABLE)
  }

  if (!response.ok) throw await toApiError(response)
  return response
}

/** Sends one request to `/api{path}` and returns the parsed JSON (undefined for 204). */
export async function request<T>(
  method: Method,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const response = await send(method, path, options)
  if (response.status === 204) return undefined as T
  return (await readJson(response)) as T
}

/**
 * The file name from a `Content-Disposition` header (`filename*=UTF-8''…` or `filename="…"`),
 * without any folder part; null when there is none.
 */
export function dispositionFileName(header: string | null): string | null {
  if (header === null) return null
  let name: string | null = null
  const extended = /filename\*\s*=\s*([^']*)'[^']*'([^;]+)/i.exec(header)
  if (extended?.[2]) {
    try {
      name = decodeURIComponent(extended[2].trim())
    } catch {
      name = null
    }
  }
  if (name === null) {
    const plain = /filename\s*=\s*(?:"((?:[^"\\]|\\.)*)"|([^;]+))/i.exec(header)
    const value = plain?.[1] ?? plain?.[2]
    if (value !== undefined) name = value.trim().replace(/\\(.)/g, '$1')
  }
  if (name === null) return null
  // A file name, never a path; no control characters.
  // eslint-disable-next-line no-control-regex
  const base = (name.split(/[/\\]/).pop() ?? '').replace(/[\u0000-\u001f\u007f]/g, '').trim()
  return base === '' || base === '.' || base === '..' ? null : base
}

/** A file the backend sends as a download: its content and the name it suggests. */
export interface Download {
  blob: Blob
  /** From `Content-Disposition`; null when the answer names no file. */
  fileName: string | null
}

/** GET `/api{path}` as a download (errors as for `request`). */
export async function download(path: string, signal?: AbortSignal): Promise<Download> {
  const response = await send('GET', path, { signal })
  return {
    blob: await response.blob(),
    fileName: dispositionFileName(response.headers.get('Content-Disposition')),
  }
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>('GET', path, { signal }),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, { body }),
  /** POST with a body sent exactly as given (JSON text). */
  postRaw: <T>(path: string, rawBody: string) => request<T>('POST', path, { rawBody }),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, { body }),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, { body }),
  delete: (path: string) => request<undefined>('DELETE', path),
}
