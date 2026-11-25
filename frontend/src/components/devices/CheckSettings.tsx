import { ChevronDown } from 'lucide-react'
import { useId } from 'react'
import {
  Controller,
  useWatch,
  type Control,
  type FieldErrors,
  type UseFormRegister,
} from 'react-hook-form'
import { Link } from 'react-router'

import type { CheckType, Device } from '@/api/types'
import { DeviceStatusSummary } from '@/components/DeviceStatusSummary'
import { FieldError, FormField } from '@/components/FormField'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useSettings } from '@/hooks/useSettings'
import {
  CHECK_FORM_FIELDS,
  CHECK_TYPE_LABELS,
  checkFieldsFor,
  sameCheck,
  type CheckFormFields,
  type DeviceFormValues,
} from '@/lib/deviceForm'
import { statusText } from '@/lib/status'
import { cn } from '@/lib/utils'

interface CheckSettingsProps {
  /** The saved device (editing), for its current status; none when adding one. */
  device?: Device
  control: Control<DeviceFormValues>
  register: UseFormRegister<DeviceFormValues>
  errors: FieldErrors<DeviceFormValues>
  checkType: CheckType
  checkEnabled: boolean
  open: boolean
  onOpenChange: (open: boolean) => void
}

const CHECK_TYPES = Object.keys(CHECK_TYPE_LABELS) as CheckType[]

/** The status check settings and the device's current status, collapsed by default. */
export function CheckSettings({
  device,
  control,
  register,
  errors,
  checkType,
  checkEnabled,
  open,
  onOpenChange,
}: CheckSettingsProps) {
  const panelId = useId()
  const enabledId = useId()
  const settings = useSettings()
  const fields = checkFieldsFor(checkType)
  const configured =
    checkType === 'none'
      ? 'No check'
      : `${CHECK_TYPE_LABELS[checkType]}, ${checkEnabled ? 'on' : 'off'}`
  // The saved check's status, while the form still describes that check.
  const watched = useWatch({ control, name: CHECK_FORM_FIELDS })
  const checkValues = Object.fromEntries(
    CHECK_FORM_FIELDS.map((field, index) => [field, watched[index]]),
  ) as CheckFormFields
  const summary =
    device && device.status !== 'off' && sameCheck(checkValues, device)
      ? `${configured} · ${statusText(device)}`
      : configured
  const hasErrors = Object.keys(errors).some((name) => name.startsWith('check_'))

  return (
    <section className="rounded-xl border bg-card">
      <h2>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => {
            onOpenChange(!open)
          }}
          className="flex w-full items-center justify-between gap-3 rounded-xl p-4 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <span className="grid gap-0.5">
            <span className="font-semibold">Status check</span>
            <span className="text-sm text-muted-foreground">
              {summary}
              {!open && hasErrors && <span className="text-destructive"> · Needs attention</span>}
            </span>
          </span>
          <ChevronDown
            aria-hidden="true"
            className={cn('size-4 transition-transform', open && 'rotate-180')}
          />
        </button>
      </h2>
      {open && (
        <div id={panelId} className="grid gap-4 border-t p-4">
          {device && (
            <div className="grid gap-1 text-sm">
              <span className="text-muted-foreground">Current status</span>
              <DeviceStatusSummary device={device} />
            </div>
          )}
          <p className="text-sm text-muted-foreground">
            {settings.data
              ? `NetScope checks every ${String(settings.data.check_interval_seconds)} s and shows a device as down after ${String(settings.data.failures_before_down)} failed ${settings.data.failures_before_down === 1 ? 'check' : 'checks in a row'} `
              : 'NetScope checks devices regularly and shows one as down after failed checks in a row '}
            (
            <Link to="/settings/status-checks" className="underline underline-offset-2">
              Settings → Status checks
            </Link>
            ). It only contacts devices whose check is turned on. Changing the check starts its
            status afresh.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Check type" error={errors.check_type?.message}>
              {(controlProps) => (
                <Controller
                  control={control}
                  name="check_type"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger
                        {...controlProps}
                        ref={field.ref}
                        onBlur={field.onBlur}
                        className="w-full"
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {CHECK_TYPES.map((type) => (
                          <SelectItem key={type} value={type}>
                            {CHECK_TYPE_LABELS[type]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              )}
            </FormField>
            <div className="grid content-start gap-1.5">
              <Label htmlFor={enabledId}>Check turned on</Label>
              <Controller
                control={control}
                name="check_enabled"
                render={({ field }) => (
                  <Switch
                    id={enabledId}
                    ref={field.ref}
                    checked={field.value}
                    onCheckedChange={field.onChange}
                    onBlur={field.onBlur}
                    aria-invalid={Boolean(errors.check_enabled)}
                    aria-describedby={errors.check_enabled ? `${enabledId}-error` : undefined}
                    className="mt-2"
                  />
                )}
              />
              <FieldError id={`${enabledId}-error`} message={errors.check_enabled?.message} />
            </div>
            {fields.has('check_port') && (
              <FormField
                label="Port"
                hint={
                  checkType === 'http' ? 'Optional: the scheme’s default (80 or 443).' : undefined
                }
                error={errors.check_port?.message}
              >
                {(controlProps) => (
                  <Input {...controlProps} {...register('check_port')} inputMode="numeric" />
                )}
              </FormField>
            )}
            {fields.has('check_scheme') && (
              <FormField label="Scheme" error={errors.check_scheme?.message}>
                {(controlProps) => (
                  <Controller
                    control={control}
                    name="check_scheme"
                    render={({ field }) => (
                      <Select value={field.value} onValueChange={field.onChange}>
                        <SelectTrigger
                          {...controlProps}
                          ref={field.ref}
                          onBlur={field.onBlur}
                          className="w-full"
                        >
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="http">http</SelectItem>
                          <SelectItem value="https">https</SelectItem>
                        </SelectContent>
                      </Select>
                    )}
                  />
                )}
              </FormField>
            )}
            {fields.has('check_path') && (
              <FormField
                label="Path"
                hint="Starts with /, for example /health."
                error={errors.check_path?.message}
              >
                {(controlProps) => (
                  <Input {...controlProps} {...register('check_path')} spellCheck={false} />
                )}
              </FormField>
            )}
            {fields.has('check_verify_tls') && (
              <div className="grid content-start gap-1.5">
                <Label htmlFor={`${enabledId}-tls`}>Verify the HTTPS certificate</Label>
                <Controller
                  control={control}
                  name="check_verify_tls"
                  render={({ field }) => (
                    <Switch
                      id={`${enabledId}-tls`}
                      ref={field.ref}
                      checked={field.value}
                      onCheckedChange={field.onChange}
                      onBlur={field.onBlur}
                      className="mt-2"
                    />
                  )}
                />
                <p className="text-xs text-muted-foreground">
                  Off by default: most home devices use self-signed certificates.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
