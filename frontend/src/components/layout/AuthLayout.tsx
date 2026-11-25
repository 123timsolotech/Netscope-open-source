import type { ReactNode } from 'react'

import { Logo } from '@/components/layout/Logo'

/** Centered card for the login and setup pages. */
export function AuthLayout({
  title,
  description,
  children,
}: {
  title: string
  description?: ReactNode
  children: ReactNode
}) {
  return (
    <main className="flex min-h-svh items-center justify-center p-4">
      <div className="grid w-full max-w-sm gap-6">
        <Logo className="justify-self-center text-lg" />
        <section className="grid gap-5 rounded-xl border bg-card p-6 text-card-foreground">
          <header className="grid gap-1">
            <h1 className="text-xl font-semibold">{title}</h1>
            {description && <p className="text-sm text-muted-foreground">{description}</p>}
          </header>
          {children}
        </section>
      </div>
    </main>
  )
}
