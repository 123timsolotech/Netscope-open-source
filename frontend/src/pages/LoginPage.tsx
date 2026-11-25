import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router'
import { z } from 'zod'

import { FormField } from '@/components/FormField'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { Notice } from '@/components/Notice'
import { ErrorState, LoadingState } from '@/components/PageStates'
import type { LoginLocationState } from '@/components/RequireAuth'
import { RetryNotice } from '@/components/RetryNotice'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useCountdown } from '@/hooks/useCountdown'
import { useCurrentUser, useLogin, useSetupStatus } from '@/hooks/useAuth'
import { handleSubmitError, type SubmitProblem } from '@/lib/forms'
import { safeNextPath } from '@/lib/redirect'

const schema = z.object({
  username: z.string().trim().min(1, 'Enter your username.'),
  password: z.string().min(1, 'Enter your password.'),
})
type LoginValues = z.infer<typeof schema>

export function LoginPage() {
  const [params] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  const setup = useSetupStatus()
  const me = useCurrentUser()
  const login = useLogin()
  const [messages, setMessages] = useState<string[]>([])
  const [retry, setRetry] = useState<SubmitProblem['retry']>(null)
  const secondsLeft = useCountdown(retry?.at ?? null)
  const sessionEnded = (location.state as LoginLocationState | null)?.sessionEnded === true

  const form = useForm<LoginValues>({
    resolver: zodResolver(schema),
    defaultValues: { username: '', password: '' },
  })
  const { errors } = form.formState
  const next = safeNextPath(params.get('next'))

  if (setup.isPending || me.isPending) return <LoadingState className="min-h-svh" />
  if (setup.isError) return <ErrorState error={setup.error} onRetry={() => void setup.refetch()} />
  if (setup.data.setup_required) return <Navigate to="/setup" replace />
  if (me.data?.user && !login.isPending) return <Navigate to={next} replace />

  const blocked = login.isPending || secondsLeft > 0

  const onSubmit = form.handleSubmit((values) => {
    setMessages([])
    login.mutate(values, {
      onSuccess: () => void navigate(next, { replace: true }),
      onError: (error) => {
        const problem = handleSubmitError(
          error,
          form.setError,
          (path) => path === 'username' || path === 'password',
        )
        setMessages(problem.messages)
        setRetry(problem.retry)
      },
    })
  })

  return (
    <AuthLayout title="Log in">
      {sessionEnded && messages.length === 0 && (
        <Notice tone="warning" title="Your session ended. Please log in again." />
      )}
      {messages.length > 0 && (
        <Notice tone="error" title={messages[0]} messages={messages.slice(1)} />
      )}
      {retry && <RetryNotice seconds={retry.seconds} secondsLeft={secondsLeft} />}
      <form
        noValidate
        onSubmit={(event) => {
          // aria-disabled, not disabled, while it runs or waits (429): the button keeps focus,
          // so Enter in a field must be ignored here too.
          if (blocked) {
            event.preventDefault()
            return
          }
          void onSubmit(event)
        }}
        className="grid gap-4"
      >
        <FormField label="Username" error={errors.username?.message}>
          {(control) => (
            <Input
              {...control}
              {...form.register('username')}
              autoComplete="username"
              autoCapitalize="none"
              dir="auto"
            />
          )}
        </FormField>
        <FormField label="Password" error={errors.password?.message}>
          {(control) => (
            <Input
              {...control}
              {...form.register('password')}
              type="password"
              autoComplete="current-password"
            />
          )}
        </FormField>
        <Button type="submit" aria-disabled={blocked || undefined}>
          {login.isPending ? 'Logging in…' : 'Log in'}
        </Button>
      </form>
    </AuthLayout>
  )
}
