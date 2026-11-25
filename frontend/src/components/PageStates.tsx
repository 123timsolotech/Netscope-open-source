import { Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'

import { Notice } from '@/components/Notice'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function LoadingState({
  label = 'Loading…',
  className,
}: {
  label?: string
  className?: string
}) {
  return (
    <div
      role="status"
      className={cn('flex items-center justify-center gap-2 p-10 text-muted-foreground', className)}
    >
      <Loader2 aria-hidden="true" className="size-4 animate-spin" />
      <span>{label}</span>
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : 'Something went wrong.'
  return (
    <div role="alert" className="grid justify-items-center gap-3 p-10 text-center">
      <p className="font-medium">Could not load this page.</p>
      <p className="text-sm text-muted-foreground">{message}</p>
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="grid justify-items-center gap-2 rounded-lg border border-dashed p-10 text-center">
      <p className="font-medium">{title}</p>
      {description && <p className="max-w-md text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

/**
 * A reload in the background failed, but the page still has what it loaded before (M6: the
 * pages poll every 30 s). The page stays, with this note, instead of an error page that would
 * drop unsaved changes; the next poll tries again.
 */
export function RefreshNotice({ error, className }: { error: unknown; className?: string }) {
  const message = error instanceof Error ? error.message : 'Something went wrong.'
  return (
    <Notice
      tone="warning"
      title="Could not load the latest data."
      messages={[message, 'This shows the last known state, so a status may be out of date.']}
      className={className}
    />
  )
}
