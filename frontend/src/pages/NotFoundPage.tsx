import { Link } from 'react-router'

import { EmptyState } from '@/components/PageStates'
import { Button } from '@/components/ui/button'
import { DEFAULT_PATH } from '@/lib/redirect'

export function NotFoundPage() {
  return (
    <div className="grid gap-6">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <EmptyState
        title="There is no page at this address."
        action={
          <Button asChild variant="outline">
            <Link to={DEFAULT_PATH}>Go to the dashboard</Link>
          </Button>
        }
      />
    </div>
  )
}
