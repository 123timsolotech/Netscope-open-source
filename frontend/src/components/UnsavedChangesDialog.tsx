import { useBeforeUnload, useBlocker } from 'react-router'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { useRegisterUnsavedChanges } from '@/hooks/unsavedChanges'

/**
 * Asks before leaving a form with unsaved changes: in-app navigation (react-router's blocker)
 * and closing or reloading the tab (the browser's own prompt). `when` is read at navigation
 * time, so pass a function that sees the latest state.
 */
export function UnsavedChangesDialog({ when }: { when: () => boolean }) {
  const blocker = useBlocker(({ currentLocation, nextLocation }) => {
    return currentLocation.pathname !== nextLocation.pathname && when()
  })

  useRegisterUnsavedChanges(when)

  useBeforeUnload((event) => {
    if (when()) event.preventDefault()
  })

  return (
    <ConfirmDialog
      open={blocker.state === 'blocked'}
      onOpenChange={(open) => {
        if (!open) blocker.reset?.()
      }}
      title="Leave without saving?"
      description="Your changes on this page will be lost."
      confirmLabel="Leave page"
      onConfirm={() => blocker.proceed?.()}
    />
  )
}
