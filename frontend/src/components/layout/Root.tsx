import { Outlet } from 'react-router'

import { Toaster } from '@/components/ui/sonner'

/** Wraps every page: the page itself plus the toast area. */
export function Root() {
  return (
    <>
      <Outlet />
      <Toaster position="bottom-right" />
    </>
  )
}
