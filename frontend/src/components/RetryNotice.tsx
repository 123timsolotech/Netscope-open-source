import { Notice } from '@/components/Notice'

interface RetryNoticeProps {
  /** The wait from Retry-After, announced once. */
  seconds: number
  /** The live countdown, only shown. */
  secondsLeft: number
}

/**
 * The 429 message with a live countdown (the backend's own text would go stale). Screen
 * readers hear it once, with the starting number; the ticking number is only shown.
 */
export function RetryNotice({ seconds, secondsLeft }: RetryNoticeProps) {
  if (secondsLeft <= 0) return null
  // Until the countdown's first tick its clock may be stale: never show more than the wait.
  const shown = Math.min(secondsLeft, seconds)
  return (
    <div role="alert">
      <span className="sr-only">{`Too many attempts. Try again in ${String(seconds)} seconds.`}</span>
      <div aria-hidden="true">
        <Notice
          tone="error"
          live={false}
          title="Too many attempts."
          messages={[`Try again in ${String(shown)} s.`]}
        />
      </div>
    </div>
  )
}
