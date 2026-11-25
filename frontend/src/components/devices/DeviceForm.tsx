import { zodResolver } from '@hookform/resolvers/zod'
import { Trash2 } from 'lucide-react'
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type SyntheticEvent,
} from 'react'
import { flushSync } from 'react-dom'
import { Controller, useForm, useWatch, type Path } from 'react-hook-form'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import type { Category, Device, DeviceSaved } from '@/api/types'
import { CategoryIcon } from '@/components/CategoryIcon'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { CheckSettings } from '@/components/devices/CheckSettings'
import { ServicesEditor } from '@/components/devices/ServicesEditor'
import { FormField } from '@/components/FormField'
import { Notice } from '@/components/Notice'
import { UnsavedChangesDialog } from '@/components/UnsavedChangesDialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useCreateDevice, useDeleteDevice, useUpdateDevice } from '@/hooks/useDevices'
import {
  deviceFormSchema,
  isVisibleDeviceField,
  toFormValues,
  toRequestBody,
  type DeviceFormValues,
} from '@/lib/deviceForm'
import { handleSubmitError } from '@/lib/forms'

/** Radix Select cannot use "" as a value; this stands for "no category". */
const NO_CATEGORY = '__none__'

export interface DeviceFormLocationState {
  /** Where "back" and a finished save go: the device list with its search and filters. */
  returnTo?: string
  /** Warnings from the save that created this device (shared IP or MAC). */
  warnings?: string[]
}

interface DeviceFormProps {
  /** Missing: a new device. */
  device?: Device
  categories: Category[]
  returnTo: string
  initialWarnings?: string[]
}

function Section({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <section className="grid gap-4 rounded-xl border bg-card p-4">
      <header className="grid gap-0.5">
        <h2 className="font-semibold">{title}</h2>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </header>
      {children}
    </section>
  )
}

export function DeviceForm({
  device,
  categories,
  returnTo,
  initialWarnings = [],
}: DeviceFormProps) {
  const navigate = useNavigate()
  const create = useCreateDevice()
  const update = useUpdateDevice()
  const remove = useDeleteDevice()
  const saving = create.isPending || update.isPending

  const [summary, setSummary] = useState<string[]>([])
  const [warnings, setWarnings] = useState<string[]>(initialWarnings)
  const warningsRef = useRef<HTMLDivElement | null>(null)
  const [checkOpen, setCheckOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  // Set right before navigating away after a save or delete, so the unsaved-changes
  // prompt does not ask about changes that were just saved.
  const leaving = useRef(false)

  const form = useForm<DeviceFormValues>({
    resolver: zodResolver(deviceFormSchema),
    defaultValues: toFormValues(device),
  })
  const { register, control, formState } = form
  const { errors, isDirty } = formState
  const checkType = useWatch({ control, name: 'check_type' })
  const checkEnabled = useWatch({ control, name: 'check_enabled' })

  /** Opens the status-check section right away (not on the next render), so its fields
   * exist when react-hook-form or we focus one of them. */
  function openCheckSection() {
    flushSync(() => {
      setCheckOpen(true)
    })
  }

  // Stable, so the app shell's registry is not updated on every render.
  const hasUnsavedChanges = useCallback(() => form.formState.isDirty && !leaving.current, [form])

  function leave(to: string, state?: DeviceFormLocationState) {
    leaving.current = true
    void navigate(to, { replace: state !== undefined, state })
  }

  // The box is at the top while the page is still scrolled to the buttons: focus it after each
  // save with warnings (which also scrolls it into view), or nothing seems to happen.
  useEffect(() => {
    if (warnings.length > 0) warningsRef.current?.focus()
  }, [warnings])

  function onSaved(saved: DeviceSaved) {
    const savedWarnings = saved.warnings.map((warning) => warning.msg)
    if (savedWarnings.length === 0) {
      toast.success(device ? `Saved ${saved.name}.` : `Added ${saved.name}.`)
      leave(returnTo)
      return
    }
    // Saved anyway (decision M3.2): stay on the device and show what to check.
    if (device) {
      form.reset(toFormValues(saved))
      setWarnings(savedWarnings)
    } else {
      leave(`/devices/${encodeURIComponent(saved.id)}`, { returnTo, warnings: savedWarnings })
    }
  }

  function onSaveError(error: Error) {
    const services = form.getValues('services').length
    const problem = handleSubmitError(
      error,
      form.setError,
      (path) => isVisibleDeviceField(path, form.getValues('check_type'), services),
      { focus: false },
    )
    setSummary(problem.messages)
    if (problem.fields.some((path) => path.startsWith('check_'))) openCheckSection()
    const [first] = problem.fields
    if (problem.fields.length === 0) {
      window.scrollTo({ top: 0 })
    } else {
      form.setFocus(first as Path<DeviceFormValues>)
    }
  }

  // handleSubmit is called inside the event handler, not during render.
  const onSubmit = (event: SyntheticEvent<HTMLFormElement>) =>
    form.handleSubmit(
      (values) => {
        setSummary([])
        setWarnings([])
        const body = toRequestBody(values)
        if (device) {
          update.mutate({ id: device.id, body }, { onSuccess: onSaved, onError: onSaveError })
        } else {
          create.mutate(body, { onSuccess: onSaved, onError: onSaveError })
        }
      },
      (invalid) => {
        // Runs before react-hook-form focuses the first invalid field.
        if (invalid.check_port) openCheckSection()
      },
    )(event)

  function onDelete() {
    if (!device) return
    setDeleteError(null)
    remove.mutate(device.id, {
      onSuccess: () => {
        toast.success(`Deleted ${device.name}.`)
        setConfirmDelete(false)
        leave(returnTo)
      },
      onError: (error) => {
        setDeleteError(error.message)
      },
    })
  }

  const fieldErrorCount = Object.keys(errors).length

  return (
    <form noValidate onSubmit={(event) => void onSubmit(event)} className="grid max-w-4xl gap-6">
      <UnsavedChangesDialog when={hasUnsavedChanges} />

      {warnings.length > 0 && (
        <div
          ref={warningsRef}
          tabIndex={-1}
          className="rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          <Notice
            tone="warning"
            title="Saved. Please check:"
            messages={warnings}
            onDismiss={() => {
              setWarnings([])
            }}
          />
        </div>
      )}
      {summary.length > 0 && (
        <Notice tone="error" title="The device was not saved." messages={summary} />
      )}
      {summary.length === 0 && fieldErrorCount > 0 && formState.isSubmitted && (
        <Notice tone="error" title="The device was not saved. Check the highlighted fields." />
      )}

      <Section title="Basics">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Name" error={errors.name?.message} className="sm:col-span-2">
            {(controlProps) => (
              <Input {...controlProps} {...register('name')} dir="auto" autoComplete="off" />
            )}
          </FormField>
          <FormField label="Category" error={errors.category_id?.message}>
            {(controlProps) => (
              <Controller
                control={control}
                name="category_id"
                render={({ field }) => (
                  <Select
                    value={field.value === '' ? NO_CATEGORY : field.value}
                    onValueChange={(value) => {
                      field.onChange(value === NO_CATEGORY ? '' : value)
                    }}
                  >
                    <SelectTrigger
                      {...controlProps}
                      ref={field.ref}
                      onBlur={field.onBlur}
                      className="w-full"
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={NO_CATEGORY}>No category</SelectItem>
                      {categories.map((category) => (
                        <SelectItem key={category.id} value={category.id}>
                          <CategoryIcon icon={category.icon} color={category.color} />
                          <span dir="auto" title={category.name} className="min-w-0 truncate">
                            {category.name}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            )}
          </FormField>
          <FormField
            label="Role"
            hint="What it does, e.g. Media server."
            error={errors.role?.message}
          >
            {(controlProps) => <Input {...controlProps} {...register('role')} dir="auto" />}
          </FormField>
          <FormField
            label="Location"
            hint="Where it is, e.g. Office shelf."
            error={errors.location?.message}
          >
            {(controlProps) => <Input {...controlProps} {...register('location')} dir="auto" />}
          </FormField>
        </div>
      </Section>

      <Section title="Addresses">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="IP address" hint="IPv4 or IPv6." error={errors.ip_address?.message}>
            {(controlProps) => (
              <Input
                {...controlProps}
                {...register('ip_address')}
                spellCheck={false}
                autoCapitalize="none"
              />
            )}
          </FormField>
          <FormField label="Hostname" error={errors.hostname?.message}>
            {(controlProps) => (
              <Input
                {...controlProps}
                {...register('hostname')}
                spellCheck={false}
                autoCapitalize="none"
              />
            )}
          </FormField>
          <FormField
            label="MAC address"
            hint="Any common format, e.g. aa:bb:cc:dd:ee:ff."
            error={errors.mac_address?.message}
          >
            {(controlProps) => (
              <Input
                {...controlProps}
                {...register('mac_address')}
                spellCheck={false}
                autoCapitalize="none"
              />
            )}
          </FormField>
          <div className="grid content-start gap-1.5">
            <Label asChild>
              <span>Vendor</span>
            </Label>
            <p className="flex h-9 items-center text-sm" dir="auto">
              {device ? (
                (device.vendor ?? <span className="text-muted-foreground">Unknown</span>)
              ) : (
                <span className="text-muted-foreground">
                  Looked up from the MAC address when you save.
                </span>
              )}
            </p>
          </div>
        </div>
      </Section>

      <Section
        title="Services"
        description="Ports and what runs on them, e.g. 8123/tcp: Home Assistant."
      >
        <ServicesEditor control={control} register={register} errors={errors} />
      </Section>

      <Section title="Notes">
        <FormField label="Description" error={errors.description?.message}>
          {(controlProps) => (
            <Textarea {...controlProps} {...register('description')} rows={4} dir="auto" />
          )}
        </FormField>
      </Section>

      <CheckSettings
        device={device}
        control={control}
        register={register}
        errors={errors}
        checkType={checkType}
        checkEnabled={checkEnabled}
        open={checkOpen}
        onOpenChange={setCheckOpen}
      />

      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={saving}>
          {saving ? 'Saving…' : device ? 'Save changes' : 'Add device'}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            void navigate(returnTo)
          }}
        >
          {isDirty ? 'Cancel' : 'Back'}
        </Button>
        {device && (
          <Button
            type="button"
            variant="destructive"
            className="ml-auto"
            onClick={() => {
              setDeleteError(null)
              setConfirmDelete(true)
            }}
          >
            <Trash2 aria-hidden="true" />
            Delete
          </Button>
        )}
      </div>

      {device && (
        <ConfirmDialog
          open={confirmDelete}
          onOpenChange={setConfirmDelete}
          title={
            <>
              Delete <span dir="auto">{device.name}</span>?
            </>
          }
          description="Its services, links and status history are deleted too. This cannot be undone."
          confirmLabel="Delete device"
          onConfirm={onDelete}
          pending={remove.isPending}
          error={deleteError}
        />
      )}
    </form>
  )
}
