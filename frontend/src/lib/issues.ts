import type { Issue } from '@/api/types'

/**
 * A 422 item's form field: `loc` without the leading "body", joined with dots
 * (["body", "services", 1, "port"] -> "services.1.port"). Null for the whole body.
 */
export function issuePath(issue: Issue): string | null {
  const parts = issue.loc[0] === 'body' ? issue.loc.slice(1) : issue.loc
  if (parts.length === 0 || issue.loc[0] === 'path' || issue.loc[0] === 'query') return null
  return parts.map(String).join('.')
}

/**
 * Splits issues into those a form can show next to a field and the rest (shown in a summary
 * at the top). `isField` decides which paths the form currently shows.
 */
export function splitIssues(
  issues: Issue[],
  isField: (path: string) => boolean,
): { fields: { path: string; message: string }[]; other: string[] } {
  const fields: { path: string; message: string }[] = []
  const other: string[] = []
  for (const issue of issues) {
    const path = issuePath(issue)
    if (path !== null && isField(path) && !fields.some((field) => field.path === path)) {
      fields.push({ path, message: issue.msg })
    } else {
      other.push(issue.msg)
    }
  }
  return { fields, other }
}
