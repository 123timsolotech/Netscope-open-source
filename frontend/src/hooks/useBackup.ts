import { useMutation, useQueryClient } from '@tanstack/react-query'

import { exportData, importData } from '@/api/backup'
import { isApiError } from '@/api/client'
import type { ImportMode } from '@/api/types'
import { queryKeys } from '@/hooks/queryClient'
import { parseForDisplay, readImportFile, RefusedFileError } from '@/lib/backup'

/** Downloads the export file (the page saves it). */
export function useExport() {
  return useMutation({ mutationFn: exportData })
}

export interface ImportRequest {
  file: Blob
  mode: ImportMode
  dryRun: boolean
}

/** Everything that shows NetScope's data: an import may have changed all of it. */
const DATA_KEYS = [
  queryKeys.devices, // the list and every device's details
  queryKeys.categories,
  queryKeys.links,
  queryKeys.dashboard,
  queryKeys.settings,
] as const

/**
 * Checks (`dryRun`) or imports the chosen file, sent as its text unchanged (refused before
 * sending if it is not UTF-8: `FileProblemError`). A refused file (422) becomes a
 * `RefusedFileError` with the file as parsed here, so the problems can name its entries.
 *
 * A real import resets every cached query that shows data (decision M8.20): they load again
 * when shown, and nothing from before the import is shown meanwhile (a device form would
 * start from old values). A dry run changes nothing, so it resets nothing.
 */
export function useImport() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async ({ file, mode, dryRun }: ImportRequest) => {
      const text = await readImportFile(file)
      try {
        return await importData(text, mode, dryRun)
      } catch (error) {
        if (isApiError(error, 422) && error.issues.length > 0) {
          throw new RefusedFileError(error.issues, parseForDisplay(text))
        }
        throw error
      }
    },
    onSuccess: (result) => {
      if (result.dry_run) return
      return Promise.all(DATA_KEYS.map((queryKey) => client.resetQueries({ queryKey })))
    },
  })
}
