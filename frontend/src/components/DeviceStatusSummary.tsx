import type { Device } from '@/api/types'
import { StatusDot } from '@/components/StatusDot'
import { failedCheckText, formatCheckedAt, statusText } from '@/lib/status'
import { cn } from '@/lib/utils'

/** The status in words, the time of the last check and why it failed (M6). */
export function DeviceStatusSummary({ device, className }: { device: Device; className?: string }) {
  if (device.status === 'off') {
    return <span className={cn('text-muted-foreground', className)}>{statusText(device)}</span>
  }
  const checked = formatCheckedAt(device)
  const failed = failedCheckText(device)
  return (
    <span className={cn('grid gap-0.5', className)}>
      <span className="flex items-center gap-1.5 font-medium">
        <StatusDot status={device.status} />
        {statusText(device)}
      </span>
      {failed !== null && (
        <span className="[overflow-wrap:anywhere] text-muted-foreground">{failed}</span>
      )}
      {checked !== null && <span className="text-muted-foreground">Last check {checked}</span>}
    </span>
  )
}
