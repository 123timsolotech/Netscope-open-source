import { z } from 'zod'

// Zod 4 tries `new Function` once to speed up parsing. NetScope's Content-Security-Policy
// forbids eval (script-src 'self'), so the attempt fails anyway, and browsers report it as a
// CSP violation. `jitless` skips the attempt; the forms parse a handful of fields, so the
// speed-up does not matter. Imported first in main.tsx, before any schema is used.
z.config({ jitless: true })
