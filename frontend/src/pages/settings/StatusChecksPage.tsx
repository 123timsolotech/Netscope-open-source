import { zodResolver } from '@hookform/resolvers/zod'
import { useCallback, useState, type SyntheticEvent } from 'react'
import { useForm, useWatch, type Path } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import type { Settings } from '@/api/types'
import { FormField } from '@/components/FormField'
import { Notice } from '@/components/Notice'
import { ErrorState, LoadingState, RefreshNotice } from '@/components/PageStates'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { UnsavedChangesDialog } from '@/components/UnsavedChangesDialog'
import { useSettings, useUpdateSettings } from '@/hooks/useSettings'
import { handleSubmitError } from '@/lib/forms'

/** Light check only (decision M4.7): whole numbers. Ranges and the timeout rule are the
 * backend's, and its 422 answer is shown next to the fields. */
const wholeNumber = z
  .string()
  .trim()
  .regex(/^\d{1,6}$/, 'Enter a whole number.')

const schema = z.object({
  check_interval_seconds: wholeNumber,
  check_timeout_seconds: wholeNumber,
  failures_before_down: wholeNumber,
  retention_days: wholeNumber,
})

type Values = z.infer<typeof schema>
type Field = keyof Values

const FIELDS = Object.keys(schema.shape) as Field[]

// Measured in M6: one stored check takes about 254 bytes, indexes included.
const BYTES_PER_CHECK = 254

function toValues(settings: Settings): Values {
  return {
    check_interval_seconds: String(settings.check_interval_seconds),
    check_timeout_seconds: String(settings.check_timeout_seconds),
    failures_before_down: String(settings.failures_before_down),
    retention_days: String(settings.retention_days),
  }
}

/** Disk space the history takes per checked device, from the values in the form. */
function historySize(values: Partial<Values>): string | null {
  const interval = Number(values.check_interval_seconds)
  const days = Number(values.retention_days)
  if (!Number.isInteger(interval) || !Number.isInteger(days) || interval <= 0 || days <= 0) {
    return null
  }
  const megabytes = (((86_400 / interval) * days * BYTES_PER_CHECK) / 1_000_000).toFixed(1)
  return `About ${megabytes} MB of history per checked device.`
}

/** Settings → Status checks (owner decision, M6): interval, timeout, threshold, history. */
export function StatusChecksPage() {
  const settings = useSettings()
  if (settings.isPending) return <LoadingState />
  // An error page only when nothing was loaded: a failed reload (on returning to the tab)
  // keeps the form and its unsaved changes.
  if (settings.data === undefined)
    return <ErrorState error={settings.error} onRetry={() => void settings.refetch()} />
  return (
    <>
      {settings.isError && <RefreshNotice error={settings.error} className="max-w-2xl" />}
      <StatusChecksForm settings={settings.data} />
    </>
  )
}

function StatusChecksForm({ settings }: { settings: Settings }) {
  const update = useUpdateSettings()
  const [summary, setSummary] = useState<string[]>([])
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: toValues(settings) })
  const { register, formState, control } = form
  // isDirty is read during render, so react-hook-form keeps it up to date (it is used
  // by the unsaved-changes prompt too).
  const { errors, isDirty, dirtyFields } = formState
  const watched = useWatch({ control })
  const size = historySize(watched)

  const hasUnsavedChanges = useCallback(() => form.formState.isDirty, [form])

  const onSubmit = (event: SyntheticEvent<HTMLFormElement>) =>
    form.handleSubmit((values) => {
      setSummary([])
      // Only what was changed: a value never changed follows the default (decision M6.2).
      const changed = FIELDS.filter((field) => dirtyFields[field])
      const body = Object.fromEntries(changed.map((field) => [field, Number(values[field])]))
      update.mutate(body, {
        onSuccess: (saved) => {
          form.reset(toValues(saved))
          toast.success('Saved the status check settings.')
        },
        onError: (error) => {
          const problem = handleSubmitError(error, form.setError, (path) =>
            FIELDS.includes(path as Field),
          )
          setSummary(problem.messages)
        },
      })
    })(event)

  return (
    <form
      noValidate
      onSubmit={(event) => void onSubmit(event)}
      className="grid max-w-2xl gap-6"
      aria-labelledby="status-checks-title"
    >
      <UnsavedChangesDialog when={hasUnsavedChanges} />
      <div className="grid gap-1">
        <h2 id="status-checks-title" className="text-lg font-semibold">
          Status checks
        </h2>
        <p className="text-sm text-muted-foreground">
          NetScope checks every device whose check is turned on, and shows it as down after several
          failed checks in a row. Changes take effect within a few seconds.
        </p>
      </div>

      {summary.length > 0 && (
        <Notice tone="error" title="Could not save the settings." messages={summary} />
      )}

      <section className="grid gap-4 rounded-xl border bg-card p-4 sm:grid-cols-2">
        <NumberField
          label="Check every"
          unit="seconds"
          hint="10 to 3600 seconds."
          error={errors.check_interval_seconds?.message}
          {...register('check_interval_seconds')}
        />
        <NumberField
          label="Timeout per check"
          unit="seconds"
          hint="1 to 30 seconds, at most half the interval."
          error={errors.check_timeout_seconds?.message}
          {...register('check_timeout_seconds')}
        />
        <NumberField
          label="Down after"
          unit="failed checks in a row"
          hint="1 to 10. One dropped ping does not make a device red."
          error={errors.failures_before_down?.message}
          {...register('failures_before_down')}
        />
        <NumberField
          label="Keep history for"
          unit="days"
          hint={`1 to 30 days. ${size ?? ''}`.trim()}
          error={errors.retention_days?.message}
          {...register('retention_days')}
        />
      </section>

      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={update.isPending}>
          {update.isPending ? 'Saving…' : 'Save settings'}
        </Button>
        {isDirty && (
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setSummary([])
              form.reset()
            }}
          >
            Discard changes
          </Button>
        )}
      </div>
    </form>
  )
}

type NumberFieldProps = ReturnType<ReturnType<typeof useForm<Values>>['register']> & {
  label: string
  unit: string
  hint: string
  error: string | undefined
  name: Path<Values>
}

function NumberField({ label, unit, hint, error, ...field }: NumberFieldProps) {
  return (
    <FormField label={label} hint={hint} error={error}>
      {(controlProps) => (
        <div className="flex items-center gap-2">
          <Input {...controlProps} {...field} inputMode="numeric" className="w-28" />
          <span className="text-sm text-muted-foreground">{unit}</span>
        </div>
      )}
    </FormField>
  )
}
