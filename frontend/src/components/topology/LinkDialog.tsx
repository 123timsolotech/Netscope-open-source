import { zodResolver } from '@hookform/resolvers/zod'
import { useState, type SyntheticEvent } from 'react'
import { Controller, useForm, type UseFormReturn } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { isApiError } from '@/api/client'
import type { Device, Link, LinkType } from '@/api/types'
import { FieldError, FormField } from '@/components/FormField'
import { Notice } from '@/components/Notice'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCreateLink, useUpdateLink } from '@/hooks/useLinks'
import { useReturnFocus } from '@/hooks/useReturnFocus'
import { handleSubmitError } from '@/lib/forms'
import { LINK_TYPES } from '@/lib/topology'
import { cn } from '@/lib/utils'

/** What the dialog is for: a new link (devices preset from a drag or a node), or a link. */
export type LinkDialogTarget =
  { kind: 'create'; deviceA?: string; deviceB?: string } | { kind: 'edit'; link: Link }

const linkTypes = LINK_TYPES.map((type) => type.value) as [LinkType, ...LinkType[]]

const schema = z.object({
  device_a_id: z.string().min(1, 'Choose a device.'),
  device_b_id: z.string().min(1, 'Choose a device.'),
  link_type: z.enum(linkTypes),
  label: z.string(),
})
type LinkValues = z.infer<typeof schema>

interface LinkDialogProps {
  target: LinkDialogTarget | null
  devices: readonly Device[]
  onOpenChange: (open: boolean) => void
  /** Edit mode: the user asked to delete the link (the page asks for confirmation). */
  onDelete: (link: Link) => void
  /** Where focus goes on close when nothing focusable opened the dialog (a line). */
  returnFocus?: () => HTMLElement | null | undefined
}

/** Add a link (asks for type and label before saving), or change a link's type and label. */
export function LinkDialog({
  target,
  devices,
  onOpenChange,
  onDelete,
  returnFocus,
}: LinkDialogProps) {
  const focus = useReturnFocus(returnFocus)
  return (
    <Dialog open={target !== null} onOpenChange={onOpenChange}>
      <DialogContent {...focus} className="max-h-[90svh] overflow-y-auto sm:max-w-md">
        {/* Remounted on every open, so it starts from the stored values. */}
        {target && (
          <LinkFormBody
            target={target}
            devices={devices}
            onDone={() => {
              onOpenChange(false)
            }}
            onDelete={onDelete}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function LinkFormBody({
  target,
  devices,
  onDone,
  onDelete,
}: {
  target: LinkDialogTarget
  devices: readonly Device[]
  onDone: () => void
  onDelete: (link: Link) => void
}) {
  const create = useCreateLink()
  const update = useUpdateLink()
  const saving = create.isPending || update.isPending
  const [summary, setSummary] = useState<string[]>([])
  const editing = target.kind === 'edit' ? target.link : null
  const nameOf = (id: string) =>
    devices.find((device) => device.id === id)?.name ?? 'Unknown device'

  const form = useForm<LinkValues>({
    resolver: zodResolver(schema),
    defaultValues: editing
      ? {
          device_a_id: editing.device_a_id,
          device_b_id: editing.device_b_id,
          link_type: editing.link_type,
          label: editing.label ?? '',
        }
      : {
          device_a_id: target.kind === 'create' ? (target.deviceA ?? '') : '',
          device_b_id: target.kind === 'create' ? (target.deviceB ?? '') : '',
          link_type: 'ethernet',
          label: '',
        },
  })
  const { errors } = form.formState
  // In edit mode the devices are text, not fields: their issues go to the summary.
  const fields = new Set(
    editing ? ['link_type', 'label'] : ['device_a_id', 'device_b_id', 'link_type', 'label'],
  )

  const onSubmit = (event: SyntheticEvent<HTMLFormElement>) =>
    form.handleSubmit((values) => {
      setSummary([])
      const onError = (error: Error) => {
        setSummary(handleSubmitError(error, form.setError, (path) => fields.has(path)).messages)
      }
      if (editing) {
        update.mutate(
          { id: editing.id, body: { link_type: values.link_type, label: values.label } },
          {
            onSuccess: () => {
              toast.success('Saved the link.')
              onDone()
            },
            onError: (error) => {
              if (isApiError(error, 404)) {
                // Deleted in another tab: the map reloads its links (useUpdateLink).
                toast.error('This link was deleted meanwhile.')
                onDone()
                return
              }
              onError(error)
            },
          },
        )
      } else {
        create.mutate(values, {
          onSuccess: () => {
            // In the order the user chose (the backend stores the smaller id first).
            toast.success(`Linked ${nameOf(values.device_a_id)} and ${nameOf(values.device_b_id)}.`)
            onDone()
          },
          onError,
        })
      }
    })(event)

  return (
    <form noValidate onSubmit={(event) => void onSubmit(event)} className="grid gap-5">
      <DialogHeader>
        <DialogTitle>{editing ? 'Edit link' : 'Add link'}</DialogTitle>
        <DialogDescription>
          {editing ? (
            <>
              Between <DeviceName name={nameOf(editing.device_a_id)} /> and{' '}
              <DeviceName name={nameOf(editing.device_b_id)} />. To connect other devices, delete
              this link and add a new one.
            </>
          ) : (
            'Links have no direction: A to B is the same as B to A.'
          )}
        </DialogDescription>
      </DialogHeader>

      {summary.length > 0 && (
        <Notice tone="error" title="The link was not saved." messages={summary} />
      )}

      {!editing && (
        <>
          <DeviceSelect
            label="From device"
            name="device_a_id"
            form={form}
            devices={devices}
            error={errors.device_a_id?.message}
          />
          <DeviceSelect
            label="To device"
            name="device_b_id"
            form={form}
            devices={devices}
            error={errors.device_b_id?.message}
          />
        </>
      )}

      <fieldset className="grid gap-2">
        <legend className="mb-2 text-sm font-medium">Type</legend>
        <Controller
          control={form.control}
          name="link_type"
          render={({ field }) => (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {LINK_TYPES.map((type) => (
                <label
                  key={type.value}
                  className={cn(
                    'flex cursor-pointer items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm has-focus-visible:ring-3 has-focus-visible:ring-ring/50',
                    field.value === type.value && 'border-primary bg-muted',
                  )}
                >
                  <input
                    type="radio"
                    name={field.name}
                    value={type.value}
                    checked={field.value === type.value}
                    onChange={() => {
                      field.onChange(type.value)
                    }}
                    onBlur={field.onBlur}
                    ref={type.value === field.value ? field.ref : undefined}
                    className="sr-only"
                  />
                  <LinkSwatch type={type.value} />
                  {type.label}
                </label>
              ))}
            </div>
          )}
        />
        <FieldError message={errors.link_type?.message} />
      </fieldset>

      <FormField
        label="Label"
        hint="Optional, shown on the line (for example a port or “LAN 1”)."
        error={errors.label?.message}
      >
        {(control) => (
          <Input {...control} {...form.register('label')} dir="auto" autoComplete="off" />
        )}
      </FormField>

      <DialogFooter className="gap-2 sm:justify-between">
        {editing ? (
          <Button
            type="button"
            variant="destructive"
            disabled={saving}
            onClick={() => {
              onDelete(editing)
            }}
          >
            Delete link
          </Button>
        ) : (
          <span />
        )}
        <div className="flex flex-col-reverse gap-2 sm:flex-row">
          <Button type="button" variant="outline" onClick={onDone}>
            Cancel
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? 'Saving…' : editing ? 'Save changes' : 'Add link'}
          </Button>
        </div>
      </DialogFooter>
    </form>
  )
}

function DeviceName({ name }: { name: string }) {
  return (
    <span dir="auto" className="font-medium text-foreground [overflow-wrap:anywhere]">
      {name}
    </span>
  )
}

function DeviceSelect({
  label,
  name,
  form,
  devices,
  error,
}: {
  label: string
  name: 'device_a_id' | 'device_b_id'
  form: UseFormReturn<LinkValues>
  devices: readonly Device[]
  error: string | undefined
}) {
  return (
    <FormField label={label} error={error}>
      {(control) => (
        <Controller
          control={form.control}
          name={name}
          render={({ field }) => (
            <Select value={field.value} onValueChange={field.onChange}>
              <SelectTrigger {...control} ref={field.ref} onBlur={field.onBlur} className="w-full">
                <SelectValue placeholder="Choose a device" />
              </SelectTrigger>
              <SelectContent>
                {devices.map((device) => (
                  <SelectItem key={device.id} value={device.id}>
                    <span dir="auto" title={device.name} className="min-w-0 truncate">
                      {device.name}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
      )}
    </FormField>
  )
}

/** A short line drawn like the link type on the map (also used by the legend). */
export function LinkSwatch({ type, className }: { type: LinkType; className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 8" className={cn('h-2 w-6 shrink-0', className)}>
      <line x1="1" y1="4" x2="23" y2="4" className={cn('map-link', `map-link-${type}`)} />
    </svg>
  )
}
