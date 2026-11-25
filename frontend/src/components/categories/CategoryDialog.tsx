import { zodResolver } from '@hookform/resolvers/zod'
import { Check } from 'lucide-react'
import { useState, type SyntheticEvent } from 'react'
import { Controller, useForm, useWatch } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import type { Category } from '@/api/types'
import { CategoryIcon } from '@/components/CategoryIcon'
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
import { useCreateCategory, useUpdateCategory } from '@/hooks/useCategories'
import { useReturnFocus } from '@/hooks/useReturnFocus'
import { COLOR_PRESETS, isHexColor, safeColor } from '@/lib/colors'
import { handleSubmitError } from '@/lib/forms'
import { CATEGORY_ICON_NAMES, isKnownIcon } from '@/lib/icons'
import { cn } from '@/lib/utils'

const schema = z.object({
  name: z.string().trim().min(1, 'Enter a name.'),
  color: z.string().refine(isHexColor, 'Pick a color.'),
  icon: z.string().min(1, 'Pick an icon.'),
})
type CategoryValues = z.infer<typeof schema>

const FIELDS = new Set(['name', 'color', 'icon'])

interface CategoryDialogProps {
  /** Missing: a new category. */
  category?: Category
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CategoryDialog({ category, open, onOpenChange }: CategoryDialogProps) {
  const focus = useReturnFocus()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent {...focus} className="max-h-[90svh] overflow-y-auto sm:max-w-lg">
        {/* Remounted on every open, so it starts from the stored values. */}
        {open && (
          <CategoryFormBody
            category={category}
            onDone={() => {
              onOpenChange(false)
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function CategoryFormBody({ category, onDone }: { category?: Category; onDone: () => void }) {
  const create = useCreateCategory()
  const update = useUpdateCategory()
  const saving = create.isPending || update.isPending
  const [summary, setSummary] = useState<string[]>([])

  const form = useForm<CategoryValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: category?.name ?? '',
      color: category ? safeColor(category.color) : (COLOR_PRESETS[0] ?? '#60a5fa'),
      icon: category?.icon ?? 'shapes',
    },
  })
  const { errors } = form.formState
  const color = useWatch({ control: form.control, name: 'color' })
  const icon = useWatch({ control: form.control, name: 'icon' })
  // A name outside the picker (set through the API) stays selectable, so editing the name or
  // color does not silently change the icon.
  const iconChoices =
    category && !isKnownIcon(category.icon)
      ? [category.icon, ...CATEGORY_ICON_NAMES]
      : CATEGORY_ICON_NAMES

  const onSubmit = (event: SyntheticEvent<HTMLFormElement>) =>
    form.handleSubmit((values) => {
      setSummary([])
      const onError = (error: Error) => {
        setSummary(handleSubmitError(error, form.setError, (path) => FIELDS.has(path)).messages)
      }
      if (category) {
        update.mutate(
          { id: category.id, body: values },
          {
            onSuccess: (saved) => {
              toast.success(`Saved ${saved.name}.`)
              onDone()
            },
            onError,
          },
        )
      } else {
        create.mutate(values, {
          onSuccess: (saved) => {
            toast.success(`Added ${saved.name}.`)
            onDone()
          },
          onError,
        })
      }
    })(event)

  return (
    <form noValidate onSubmit={(event) => void onSubmit(event)} className="grid gap-5">
      <DialogHeader>
        <DialogTitle>{category ? 'Edit category' : 'Add category'}</DialogTitle>
        <DialogDescription>Name, color and icon, as shown in the device list.</DialogDescription>
      </DialogHeader>

      {summary.length > 0 && (
        <Notice tone="error" title="The category was not saved." messages={summary} />
      )}

      <FormField label="Name" error={errors.name?.message}>
        {(control) => (
          <Input {...control} {...form.register('name')} dir="auto" autoComplete="off" />
        )}
      </FormField>

      <fieldset className="grid gap-2">
        <legend className="mb-2 text-sm font-medium">Color</legend>
        <Controller
          control={form.control}
          name="color"
          render={({ field }) => (
            <div className="flex flex-wrap items-center gap-2">
              {COLOR_PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  aria-label={`Color ${preset}`}
                  aria-pressed={field.value.toLowerCase() === preset}
                  onClick={() => {
                    field.onChange(preset)
                  }}
                  className="flex size-7 items-center justify-center rounded-full ring-offset-2 ring-offset-background outline-none focus-visible:ring-3 focus-visible:ring-ring aria-pressed:ring-2 aria-pressed:ring-foreground"
                  style={{ backgroundColor: preset }}
                >
                  {field.value.toLowerCase() === preset && (
                    <Check aria-hidden="true" className="size-4 text-primary-foreground" />
                  )}
                </button>
              ))}
              <label className="ml-1 inline-flex items-center gap-2 text-sm text-muted-foreground">
                <input
                  ref={field.ref}
                  type="color"
                  value={safeColor(field.value)}
                  onChange={(event) => {
                    field.onChange(event.target.value)
                  }}
                  onBlur={field.onBlur}
                  className="size-8 cursor-pointer rounded-md border bg-transparent p-0.5"
                />
                Other color
              </label>
            </div>
          )}
        />
        <p className="text-xs text-muted-foreground">
          Selected: <span className="font-mono">{color.toLowerCase()}</span>
        </p>
        <FieldError message={errors.color?.message} />
      </fieldset>

      <fieldset className="grid gap-2">
        <legend className="mb-2 text-sm font-medium">Icon</legend>
        <Controller
          control={form.control}
          name="icon"
          render={({ field }) => (
            <div className="grid grid-cols-8 gap-1 sm:grid-cols-10">
              {iconChoices.map((name, index) => (
                <button
                  key={name}
                  ref={index === 0 ? field.ref : undefined}
                  type="button"
                  aria-label={name}
                  title={name}
                  aria-pressed={field.value === name}
                  onClick={() => {
                    field.onChange(name)
                  }}
                  className={cn(
                    'flex aspect-square items-center justify-center rounded-md border border-transparent outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50',
                    field.value === name && 'border-ring bg-muted',
                  )}
                >
                  <CategoryIcon
                    icon={name}
                    color={field.value === name ? color : undefined}
                    className="size-5"
                  />
                </button>
              ))}
            </div>
          )}
        />
        <p className="text-xs text-muted-foreground">
          Selected: <span className="font-mono">{icon}</span>
        </p>
        <FieldError message={errors.icon?.message} />
      </fieldset>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" disabled={saving}>
          {saving ? 'Saving…' : category ? 'Save changes' : 'Add category'}
        </Button>
      </DialogFooter>
    </form>
  )
}
