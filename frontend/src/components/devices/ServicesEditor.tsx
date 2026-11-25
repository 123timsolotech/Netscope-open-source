import { Plus, Trash2 } from 'lucide-react'
import {
  Controller,
  useFieldArray,
  type Control,
  type FieldErrors,
  type UseFormRegister,
} from 'react-hook-form'

import { FieldError } from '@/components/FormField'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { EMPTY_SERVICE, type DeviceFormValues } from '@/lib/deviceForm'

interface ServicesEditorProps {
  control: Control<DeviceFormValues>
  register: UseFormRegister<DeviceFormValues>
  errors: FieldErrors<DeviceFormValues>
}

type ServiceField = keyof DeviceFormValues['services'][number]

/** react-hook-form's typed path to one service's field ("services.1.port"). */
function servicePath<F extends ServiceField>(index: number, field: F): `services.${number}.${F}` {
  // eslint-disable-next-line @typescript-eslint/restrict-template-expressions -- typed path
  return `services.${index}.${field}`
}

/** One row per service; the whole list replaces the stored one on save (decision M3.3). */
export function ServicesEditor({ control, register, errors }: ServicesEditorProps) {
  const { fields, append, remove } = useFieldArray({ control, name: 'services' })

  return (
    <div className="grid gap-3">
      {fields.length === 0 && <p className="text-sm text-muted-foreground">No services yet.</p>}
      {fields.map((field, index) => {
        const number = index + 1
        const rowErrors = errors.services?.[index]
        const errorId = (name: string) => `service-${String(index)}-${name}-error`
        const described = (name: 'port' | 'name' | 'note' | 'protocol') =>
          rowErrors?.[name]?.message ? errorId(name) : undefined
        return (
          <div
            key={field.id}
            role="group"
            aria-label={`Service ${String(number)}`}
            className="grid grid-cols-[6rem_6rem_1fr] gap-2 rounded-lg border p-3 sm:grid-cols-[6rem_6rem_1fr_1fr_auto] sm:items-start"
          >
            <div className="grid gap-1">
              <Input
                {...register(servicePath(index, 'port'))}
                aria-label={`Service ${String(number)} port`}
                aria-invalid={Boolean(rowErrors?.port)}
                aria-describedby={described('port')}
                placeholder="Port"
                inputMode="numeric"
              />
              <FieldError id={errorId('port')} message={rowErrors?.port?.message} />
            </div>
            <div className="grid gap-1">
              <Controller
                control={control}
                name={servicePath(index, 'protocol')}
                render={({ field: protocol }) => (
                  <Select value={protocol.value} onValueChange={protocol.onChange}>
                    <SelectTrigger
                      ref={protocol.ref}
                      onBlur={protocol.onBlur}
                      aria-label={`Service ${String(number)} protocol`}
                      aria-invalid={Boolean(rowErrors?.protocol)}
                      aria-describedby={described('protocol')}
                      className="w-full"
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="tcp">TCP</SelectItem>
                      <SelectItem value="udp">UDP</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
              <FieldError id={errorId('protocol')} message={rowErrors?.protocol?.message} />
            </div>
            <div className="grid gap-1">
              <Input
                {...register(servicePath(index, 'name'))}
                aria-label={`Service ${String(number)} name`}
                aria-invalid={Boolean(rowErrors?.name)}
                aria-describedby={described('name')}
                placeholder="Name, e.g. Home Assistant"
                dir="auto"
              />
              <FieldError id={errorId('name')} message={rowErrors?.name?.message} />
            </div>
            <div className="col-span-2 grid gap-1 sm:col-span-1">
              <Input
                {...register(servicePath(index, 'note'))}
                aria-label={`Service ${String(number)} note`}
                aria-invalid={Boolean(rowErrors?.note)}
                aria-describedby={described('note')}
                placeholder="Note (optional)"
                dir="auto"
              />
              <FieldError id={errorId('note')} message={rowErrors?.note?.message} />
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={`Remove service ${String(number)}`}
              onClick={() => {
                remove(index)
              }}
              className="justify-self-end"
            >
              <Trash2 />
            </Button>
          </div>
        )
      })}
      <Button
        type="button"
        variant="outline"
        className="justify-self-start"
        onClick={() => {
          append({ ...EMPTY_SERVICE }, { focusName: `services.${String(fields.length)}.port` })
        }}
      >
        <Plus aria-hidden="true" />
        Add service
      </Button>
    </div>
  )
}
