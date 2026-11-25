import { api, download } from '@/api/client'
import type { ImportMode, ImportResult } from '@/api/types'

/** The name the export is saved under when the answer names none. */
export const EXPORT_FALLBACK_NAME = 'netscope-export.json'

export interface ExportDownload {
  blob: Blob
  /** The server's file name (`netscope-export-YYYY-MM-DD.json`), or the fallback. */
  fileName: string
}

/** Everything the user entered, as the export file (M8). */
export async function exportData(): Promise<ExportDownload> {
  const file = await download('/export')
  return { blob: file.blob, fileName: file.fileName ?? EXPORT_FALLBACK_NAME }
}

/**
 * Checks (`dryRun`) or imports an export file. `text` is the chosen file's text, sent as it
 * is: the backend parses and checks it, and answers 422 with every problem (`loc` points into
 * the file), 413 above its size limit, 409 if NetScope's data changed meanwhile.
 */
export function importData(text: string, mode: ImportMode, dryRun: boolean): Promise<ImportResult> {
  const query = new URLSearchParams({ mode, dry_run: String(dryRun) })
  return api.postRaw<ImportResult>(`/import?${query.toString()}`, text)
}
