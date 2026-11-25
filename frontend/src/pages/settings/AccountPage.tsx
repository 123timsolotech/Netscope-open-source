import { zodResolver } from '@hookform/resolvers/zod'
import { useState, type ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { FormField } from '@/components/FormField'
import { Notice } from '@/components/Notice'
import { RetryNotice } from '@/components/RetryNotice'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useCountdown } from '@/hooks/useCountdown'
import { useChangePassword, useCurrentUser, useLogoutOthers, useSessions } from '@/hooks/useAuth'
import { characterCount, handleSubmitError, type SubmitProblem } from '@/lib/forms'

/** Light checks only (decision M4.7): the backend's length rule (counted in code points like
 * Python) and the repeat. Whether the current password is right is the backend's answer. */
const schema = z
  .object({
    current_password: z.string().min(1, 'Enter your current password.'),
    new_password: z
      .string()
      .refine((value) => characterCount(value) >= 20, 'Use at least 20 characters.')
      .refine((value) => characterCount(value) <= 1024, 'Use at most 1024 characters.'),
    confirm: z.string(),
  })
  .refine((values) => values.new_password === values.confirm, {
    path: ['confirm'],
    message: 'The passwords do not match.',
  })
type PasswordValues = z.infer<typeof schema>

const EMPTY: PasswordValues = { current_password: '', new_password: '', confirm: '' }
const FIELDS = new Set(['current_password', 'new_password'])

function otherSessionsText(count: number): string {
  if (count === 0) return 'No other sessions are logged in.'
  if (count === 1) return '1 other session is logged in.'
  return `${String(count)} other sessions are logged in.`
}

function Card({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="grid gap-4 rounded-xl border bg-card p-4 sm:p-5">
      <h3 id={id} className="font-medium">
        {title}
      </h3>
      {children}
    </section>
  )
}

/** Settings → Account (owner decision, M8): change the password, log out other sessions. */
export function AccountPage() {
  return (
    <div className="grid max-w-2xl gap-6">
      <div className="grid gap-1">
        <h2 className="text-lg font-semibold">Account</h2>
        <p className="text-sm text-muted-foreground">
          Your password and the browsers that are logged in.
        </p>
      </div>
      <ChangePassword />
      <OtherSessions />
    </div>
  )
}

/**
 * No unsaved-changes prompt here: a half-typed password is not worth keeping, and leaving the
 * page should drop it.
 */
function ChangePassword() {
  const me = useCurrentUser()
  const change = useChangePassword()
  const [messages, setMessages] = useState<string[]>([])
  const [retry, setRetry] = useState<SubmitProblem['retry']>(null)
  const secondsLeft = useCountdown(retry?.at ?? null)
  const form = useForm<PasswordValues>({ resolver: zodResolver(schema), defaultValues: EMPTY })
  const { errors } = form.formState

  const blocked = change.isPending || secondsLeft > 0

  const onSubmit = form.handleSubmit(({ current_password, new_password }) => {
    setMessages([])
    setRetry(null)
    change.mutate(
      { current_password, new_password },
      {
        onSuccess: () => {
          form.reset(EMPTY)
          toast.success('Password changed. Other sessions were logged out.')
        },
        onError: (error) => {
          const problem = handleSubmitError(error, form.setError, (path) => FIELDS.has(path))
          setMessages(problem.messages)
          setRetry(problem.retry)
        },
      },
    )
  })

  return (
    <Card id="account-password" title="Change password">
      {messages.length > 0 && (
        <Notice tone="error" title={messages[0]} messages={messages.slice(1)} />
      )}
      {retry && <RetryNotice seconds={retry.seconds} secondsLeft={secondsLeft} />}
      <form
        noValidate
        onSubmit={(event) => {
          // aria-disabled, not disabled, while it runs or waits: the button keeps focus, so
          // Enter in a field must be ignored here too.
          if (blocked) {
            event.preventDefault()
            return
          }
          void onSubmit(event)
        }}
        aria-labelledby="account-password"
        className="grid gap-4"
      >
        {/* For password managers: which account this new password belongs to. */}
        <input
          type="text"
          name="username"
          autoComplete="username"
          value={me.data?.user?.username ?? ''}
          readOnly
          hidden
        />
        <FormField label="Current password" error={errors.current_password?.message}>
          {(control) => (
            <Input
              {...control}
              {...form.register('current_password')}
              type="password"
              autoComplete="current-password"
            />
          )}
        </FormField>
        <FormField
          label="New password"
          hint="At least 20 characters. A few random words make a good one."
          error={errors.new_password?.message}
        >
          {(control) => (
            <Input
              {...control}
              {...form.register('new_password')}
              type="password"
              autoComplete="new-password"
            />
          )}
        </FormField>
        <FormField label="Repeat new password" error={errors.confirm?.message}>
          {(control) => (
            <Input
              {...control}
              {...form.register('confirm')}
              type="password"
              autoComplete="new-password"
            />
          )}
        </FormField>
        <p className="text-sm text-muted-foreground">
          Every other browser is logged out; this one stays logged in.
        </p>
        <div>
          <Button type="submit" aria-disabled={blocked || undefined}>
            {change.isPending ? 'Changing password…' : 'Change password'}
          </Button>
        </div>
      </form>
    </Card>
  )
}

function OtherSessions() {
  const sessions = useSessions()
  const logoutOthers = useLogoutOthers()
  const [error, setError] = useState<string | null>(null)
  const count = sessions.data?.other_sessions

  // aria-disabled, not disabled: the button keeps focus while it runs and once none is left.
  const unavailable = count === undefined || count === 0 || logoutOthers.isPending

  function onLogoutOthers() {
    if (unavailable) return
    setError(null)
    logoutOthers.mutate(undefined, {
      onSuccess: () => {
        toast.success('Other sessions were logged out.')
      },
      onError: (failure) => {
        setError(failure.message)
      },
    })
  }

  return (
    <Card id="account-sessions" title="Sessions">
      {count === undefined ? (
        sessions.isError ? (
          <div className="grid justify-items-start gap-2">
            <Notice
              tone="error"
              title="Could not load the sessions."
              messages={[sessions.error.message]}
            />
            <Button variant="outline" size="sm" onClick={() => void sessions.refetch()}>
              Try again
            </Button>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Loading…</p>
        )
      ) : (
        <p className="text-sm">{otherSessionsText(count)}</p>
      )}
      {error && (
        <Notice tone="error" title="Could not log out the other sessions." messages={[error]} />
      )}
      <p className="text-sm text-muted-foreground">
        A session ends 30 days after its last use, and at most 90 days after logging in.
      </p>
      <div>
        <Button variant="outline" aria-disabled={unavailable || undefined} onClick={onLogoutOthers}>
          {logoutOthers.isPending ? 'Logging out…' : 'Log out other sessions'}
        </Button>
      </div>
    </Card>
  )
}
