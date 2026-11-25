import { createContext, useContext, useEffect, useMemo, useRef } from 'react'

/**
 * Which open forms have unsaved changes, for actions that leave the page without a
 * navigation the router could block: logging out unmounts the whole app shell first.
 */
export interface UnsavedChangesRegistry {
  register: (hasChanges: () => boolean) => () => void
  hasUnsavedChanges: () => boolean
}

export const UnsavedChangesContext = createContext<UnsavedChangesRegistry | null>(null)

export function useUnsavedChangesRegistry(): UnsavedChangesRegistry {
  const checks = useRef(new Set<() => boolean>())
  return useMemo(
    () => ({
      register: (hasChanges) => {
        checks.current.add(hasChanges)
        return () => {
          checks.current.delete(hasChanges)
        }
      },
      hasUnsavedChanges: () => [...checks.current].some((hasChanges) => hasChanges()),
    }),
    [],
  )
}

/** Tells the app shell (if any) about a form's unsaved changes while it is mounted. */
export function useRegisterUnsavedChanges(hasChanges: () => boolean): void {
  const registry = useContext(UnsavedChangesContext)
  useEffect(() => registry?.register(hasChanges), [registry, hasChanges])
}
