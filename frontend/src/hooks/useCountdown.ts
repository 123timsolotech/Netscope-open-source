import { useEffect, useState } from 'react'

/**
 * Seconds left until `until` (a Date.now() timestamp), updated every second; 0 when there is
 * nothing to wait for.
 */
export function useCountdown(until: number | null): number {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (until === null) return
    const tick = () => {
      const current = Date.now()
      setNow(current)
      if (current >= until) window.clearInterval(timer)
    }
    const first = window.setTimeout(tick, 0)
    const timer = window.setInterval(tick, 1000)
    return () => {
      window.clearTimeout(first)
      window.clearInterval(timer)
    }
  }, [until])

  return until === null ? 0 : Math.max(0, Math.ceil((until - now) / 1000))
}
