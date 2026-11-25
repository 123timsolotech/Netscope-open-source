import { useRef } from 'react'

/**
 * Focus handling for dialogs opened without a Radix Trigger (from a menu, a table row or a
 * navigation prompt): Radix would return focus to the missing trigger, which leaves it on
 * <body>. This remembers what had focus when the dialog opened and returns there on close;
 * if that element is gone (a deleted row), `fallback` gives another target.
 */
export function useReturnFocus(fallback?: () => HTMLElement | null | undefined) {
  const opener = useRef<HTMLElement | null>(null)
  return {
    onOpenAutoFocus: () => {
      const active = document.activeElement
      opener.current = active instanceof HTMLElement && active !== document.body ? active : null
    },
    onCloseAutoFocus: (event: Event) => {
      const target = [opener.current, fallback?.()].find((element) => element?.isConnected)
      if (target) {
        event.preventDefault()
        target.focus()
      }
    },
  }
}
