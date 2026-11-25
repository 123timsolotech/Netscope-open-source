import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'

import { isApiError } from '@/api/client'
import { splitIssues } from '@/lib/issues'

export interface SubmitProblem {
  /** Messages for the summary at the top of the form. */
  messages: string[]
  /** Fields that got an error, in the backend's order (the first one gets focus). */
  fields: string[]
  /** Set for 429: when to try again (Date.now() milliseconds) and the wait in seconds. */
  retry: { at: number; seconds: number } | null
}

/**
 * Turns a failed save into field errors (422 items whose `loc` names a field the form shows)
 * and a summary for everything else. By default the first field error gets focus.
 */
export function handleSubmitError<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  isField: (path: string) => boolean,
  { focus = true }: { focus?: boolean } = {},
): SubmitProblem {
  if (isApiError(error, 422) && error.issues.length > 0) {
    const { fields, other } = splitIssues(error.issues, isField)
    fields.forEach((field, index) => {
      setError(
        field.path as Path<T>,
        { type: 'server', message: field.message },
        { shouldFocus: focus && index === 0 },
      )
    })
    return { messages: other, fields: fields.map((field) => field.path), retry: null }
  }
  if (isApiError(error, 429)) {
    const seconds = error.retryAfter ?? 60
    return { messages: [], fields: [], retry: { at: Date.now() + seconds * 1000, seconds } }
  }
  const message = error instanceof Error ? error.message : 'Something went wrong.'
  return { messages: [message], fields: [], retry: null }
}

/** Length in characters as the backend counts them (code points, not UTF-16 units). */
export function characterCount(value: string): number {
  // Each surrogate pair (emoji and other characters outside the BMP) is one code point.
  return value.replace(/[\uD800-\uDBFF][\uDC00-\uDFFF]/g, '_').length
}
