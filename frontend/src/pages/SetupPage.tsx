import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useNavigate } from 'react-router'
import { toast } from 'sonner'
import { z } from 'zod'

import { isApiError } from '@/api/client'
import type { SetupStatus } from '@/api/types'
import { FormField } from '@/components/FormField'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { Notice } from '@/components/Notice'
import { ErrorState, LoadingState } from '@/components/PageStates'
import { RetryNotice } from '@/components/RetryNotice'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/hooks/queryClient'
import { useCompleteSetup, useSetupStatus } from '@/hooks/useAuth'
import { useCountdown } from '@/hooks/useCountdown'
import { characterCount, handleSubmitError, type SubmitProblem } from '@/lib/forms'
import { DEFAULT_PATH } from '@/lib/redirect'

// The same rules as the backend (brief section 7), checked here first so a typo does not use
// up one of the five setup attempts per minute. The backend still decides.
const USERNAME = /^[A-Za-z0-9._-]{3,64}$/
const schema = z
  .object({
    setup_token: z.string().trim().min(1, 'Enter the setup token from the NetScope log.'),
    username: z
      .string()
      .trim()
      .regex(USERNAME, 'Use 3–64 letters, digits, dots, underscores or hyphens.'),
    password: z
      .string()
      .refine((value) => characterCount(value) >= 20, 'Use at least 20 characters.')
      .refine((value) => characterCount(value) <= 1024, 'Use at most 1024 characters.'),
    confirm: z.string(),
  })
  .refine((values) => values.password === values.confirm, {
    path: ['confirm'],
    message: 'The passwords do not match.',
  })
type SetupValues = z.infer<typeof schema>

const FIELDS = new Set(['setup_token', 'username', 'password'])

export function SetupPage() {
  const navigate = useNavigate()
  const client = useQueryClient()
  const setup = useSetupStatus()
  const complete = useCompleteSetup()
  const [messages, setMessages] = useState<string[]>([])
  const [retry, setRetry] = useState<SubmitProblem['retry']>(null)
  const secondsLeft = useCountdown(retry?.at ?? null)

  const form = useForm<SetupValues>({
    resolver: zodResolver(schema),
    defaultValues: { setup_token: '', username: 'admin', password: '', confirm: '' },
  })
  const { errors } = form.formState

  if (setup.isPending) return <LoadingState className="min-h-svh" />
  if (setup.isError) return <ErrorState error={setup.error} onRetry={() => void setup.refetch()} />
  if (!setup.data.setup_required && !complete.isPending && !complete.isSuccess)
    return <Navigate to="/login" replace />

  const blocked = complete.isPending || secondsLeft > 0

  const onSubmit = form.handleSubmit(({ setup_token, username, password }) => {
    setMessages([])
    complete.mutate(
      { setup_token, username, password },
      {
        onSuccess: () => {
          toast.success('Admin account created.')
          void navigate(DEFAULT_PATH, { replace: true })
        },
        onError: (error) => {
          if (isApiError(error, 403)) {
            form.setError(
              'setup_token',
              { type: 'server', message: error.message },
              { shouldFocus: true },
            )
            return
          }
          if (isApiError(error, 409)) {
            // Someone finished setup meanwhile (another tab, NETSCOPE_ADMIN_PASSWORD).
            toast.info('Setup is already done. Please log in.')
            client.setQueryData<SetupStatus>(queryKeys.setup, { setup_required: false })
            void navigate('/login', { replace: true })
            return
          }
          const problem = handleSubmitError(error, form.setError, (path) => FIELDS.has(path))
          setMessages(problem.messages)
          setRetry(problem.retry)
        },
      },
    )
  })

  return (
    <AuthLayout
      title="Set up NetScope"
      description="Create the admin account. The one-time setup token is printed in the NetScope log."
    >
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
        <FormField label="Setup token" error={errors.setup_token?.message}>
          {(control) => (
            <Input
              {...control}
              {...form.register('setup_token')}
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
            />
          )}
        </FormField>
        <FormField
          label="Username"
          hint="3–64 characters: letters, digits, dots, underscores or hyphens."
          error={errors.username?.message}
        >
          {(control) => (
            <Input
              {...control}
              {...form.register('username')}
              autoComplete="username"
              autoCapitalize="none"
            />
          )}
        </FormField>
        <FormField
          label="Password"
          hint="At least 20 characters. A few random words make a good one."
          error={errors.password?.message}
        >
          {(control) => (
            <Input
              {...control}
              {...form.register('password')}
              type="password"
              autoComplete="new-password"
            />
          )}
        </FormField>
        <FormField label="Repeat password" error={errors.confirm?.message}>
          {(control) => (
            <Input
              {...control}
              {...form.register('confirm')}
              type="password"
              autoComplete="new-password"
            />
          )}
        </FormField>
        <Button type="submit" aria-disabled={blocked || undefined}>
          {complete.isPending ? 'Creating account…' : 'Create admin account'}
        </Button>
      </form>
    </AuthLayout>
  )
}
