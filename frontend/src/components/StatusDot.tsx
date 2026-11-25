import type { DeviceStatus } from '@/api/types'
import { cn } from '@/lib/utils'

interface StatusDotProps {
  status: DeviceStatus
  className?: string
}

/**
 * A device's status as a small round sign whose shape differs as well as its color (owner
 * decision, M6): a check mark when up, a cross when down, a dashed ring while waiting for a
 * check, a clock when there was no recent check. Nothing when the check is off. Decorative:
 * the words come from `STATUS_LABELS` next to it or in the element's label.
 */
export function StatusDot({ status, className }: StatusDotProps) {
  if (status === 'off') return null
  return (
    <svg
      viewBox="0 0 16 16"
      aria-hidden="true"
      data-status={status}
      className={cn('size-3.5 shrink-0', className)}
    >
      {status === 'up' && (
        <>
          <circle cx="8" cy="8" r="8" className="fill-status-up" />
          <path
            d="M4.5 8.3 7 10.7l4.6-5"
            fill="none"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="stroke-background"
          />
        </>
      )}
      {status === 'down' && (
        <>
          <circle cx="8" cy="8" r="8" className="fill-status-down" />
          <path
            d="m5.2 5.2 5.6 5.6m0-5.6-5.6 5.6"
            fill="none"
            strokeWidth="2"
            strokeLinecap="round"
            className="stroke-background"
          />
        </>
      )}
      {status === 'waiting' && (
        <circle
          cx="8"
          cy="8"
          r="6.5"
          fill="none"
          strokeWidth="2.5"
          strokeDasharray="3.4 2.4"
          className="stroke-status-unknown"
        />
      )}
      {status === 'stale' && (
        <>
          <circle cx="8" cy="8" r="8" className="fill-status-unknown" />
          <path
            d="M8 4.2V8l2.6 1.8"
            fill="none"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="stroke-background"
          />
        </>
      )}
    </svg>
  )
}
