import { useRouteError } from 'react-router'

import { Button } from '@/components/ui/button'
import { DEFAULT_PATH } from '@/lib/redirect'

/** Last resort when a page throws while rendering. */
export function RouteErrorPage() {
  const error = useRouteError()
  console.error(error)
  return (
    <main
      role="alert"
      className="grid min-h-svh place-content-center justify-items-center gap-3 p-4 text-center"
    >
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        NetScope hit an unexpected error on this page. Reloading usually helps.
      </p>
      <div className="flex gap-2">
        <Button
          onClick={() => {
            window.location.reload()
          }}
        >
          Reload
        </Button>
        {/* A full page load: the router itself may be what failed. */}
        <Button asChild variant="outline">
          <a href={DEFAULT_PATH}>Go to the dashboard</a>
        </Button>
      </div>
    </main>
  )
}
