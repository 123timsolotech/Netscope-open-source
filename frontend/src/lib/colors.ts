const HEX_COLOR = /^#[0-9a-fA-F]{6}$/

/** The default categories' colors (backend seed data) as quick picks. */
export const COLOR_PRESETS = [
  '#60a5fa',
  '#818cf8',
  '#a78bfa',
  '#c084fc',
  '#e879f9',
  '#f472b6',
  '#f0abfc',
  '#fdba74',
  '#bef264',
  '#5eead4',
  '#7dd3fc',
  '#94a3b8',
]

export const FALLBACK_COLOR = '#94a3b8'

export function isHexColor(value: string): boolean {
  return HEX_COLOR.test(value)
}

/** A color safe to put in a style: the stored value if it is #rrggbb, else a neutral gray. */
export function safeColor(value: string | null | undefined): string {
  return value && isHexColor(value) ? value : FALLBACK_COLOR
}
