import { CircleAlert, CircleCheck, TriangleAlert, X } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const TONES = {
  error: {
    icon: CircleAlert,
    box: 'border-destructive/40 bg-destructive/10',
    color: 'text-destructive',
    role: 'alert',
  },
  warning: {
    icon: TriangleAlert,
    box: 'border-status-warn/40 bg-status-warn/10',
    color: 'text-status-warn',
    role: 'status',
  },
  success: {
    icon: CircleCheck,
    box: 'border-status-up/40 bg-status-up/10',
    color: 'text-status-up',
    role: 'status',
  },
} as const

interface NoticeProps {
  tone: keyof typeof TONES
  /** Announce to screen readers (alert / status). Off when a wrapper announces instead. */
  live?: boolean
  title: ReactNode
  /** Plain-text messages (from the backend: never rendered as HTML). */
  messages?: string[]
  /** A plain-text line under the messages. */
  note?: string
  onDismiss?: () => void
  className?: string
}

/** A box at the top of a form or page: errors that belong to no field, warnings after saving,
 * or what a finished action did. */
export function Notice({
  tone,
  live = true,
  title,
  messages = [],
  note,
  onDismiss,
  className,
}: NoticeProps) {
  const style = TONES[tone]
  const Icon = style.icon
  return (
    <div
      role={live ? style.role : undefined}
      className={cn(
        'flex gap-3 rounded-lg border p-3 text-sm text-foreground',
        style.box,
        className,
      )}
    >
      <Icon aria-hidden="true" className={cn('mt-0.5 size-4 shrink-0', style.color)} />
      <div className="grid min-w-0 flex-1 gap-1">
        <p className="font-medium">{title}</p>
        {messages.length > 0 && (
          <ul className="grid list-disc gap-0.5 pl-4 text-muted-foreground">
            {messages.map((message, index) => (
              <li key={index} dir="auto" className="[overflow-wrap:anywhere]">
                {message}
              </li>
            ))}
          </ul>
        )}
        {note && <p className="text-muted-foreground">{note}</p>}
      </div>
      {onDismiss && (
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label="Dismiss"
          onClick={onDismiss}
        >
          <X />
        </Button>
      )}
    </div>
  )
}
