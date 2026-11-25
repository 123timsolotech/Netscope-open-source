/**
 * Saves `blob` as a file named `fileName` (the browser's download), through an object URL and
 * a temporary link. The URL is revoked a moment later: some browsers read it only after the
 * click has returned.
 */
export const REVOKE_AFTER_MS = 1000

export function saveFile(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.hidden = true
  document.body.append(link)
  link.click()
  link.remove()
  window.setTimeout(() => {
    URL.revokeObjectURL(url)
  }, REVOKE_AFTER_MS)
}
