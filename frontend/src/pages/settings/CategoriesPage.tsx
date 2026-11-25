import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import type { Category } from '@/api/types'
import { CategoryDialog } from '@/components/categories/CategoryDialog'
import { CategoryIcon } from '@/components/CategoryIcon'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { EmptyState, ErrorState, LoadingState, RefreshNotice } from '@/components/PageStates'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useCategories, useDeleteCategory } from '@/hooks/useCategories'
import { compareText } from '@/lib/sort'

function devicesText(count: number): string {
  return `${String(count)} ${count === 1 ? 'device' : 'devices'}`
}

export function CategoriesPage() {
  const categories = useCategories()
  const remove = useDeleteCategory()
  const [editing, setEditing] = useState<Category | null>(null)
  const [creating, setCreating] = useState(false)
  const [toDelete, setToDelete] = useState<Category | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  // Focus after deleting a category (its row and buttons are gone).
  const addButton = useRef<HTMLButtonElement | null>(null)

  if (categories.isPending) return <LoadingState />
  // An error page only when nothing was loaded: a failed reload keeps the page (and an open
  // dialog).
  if (categories.data === undefined)
    return <ErrorState error={categories.error} onRetry={() => void categories.refetch()} />

  const sorted = [...categories.data].sort((a, b) => compareText(a.name, b.name))

  function confirmDelete() {
    if (!toDelete) return
    const category = toDelete
    setDeleteError(null)
    remove.mutate(category.id, {
      onSuccess: () => {
        toast.success(`Deleted ${category.name}.`)
        setToDelete(null)
      },
      onError: (error) => {
        setDeleteError(error.message)
      },
    })
  }

  return (
    <section className="grid gap-4">
      {categories.isError && <RefreshNotice error={categories.error} />}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Categories</h2>
          <p className="text-sm text-muted-foreground">
            Group devices by kind. Each has a color and an icon.
          </p>
        </div>
        <Button
          ref={addButton}
          onClick={() => {
            setCreating(true)
          }}
        >
          <Plus aria-hidden="true" />
          Add category
        </Button>
      </div>

      {sorted.length === 0 ? (
        <EmptyState
          title="No categories"
          description={
            <>
              Add one, or run <code className="font-mono">netscope seed</code> to bring back the 12
              default categories.
            </>
          }
        />
      ) : (
        <div className="rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Devices</TableHead>
                <TableHead className="w-24">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.map((category) => (
                <TableRow key={category.id}>
                  <TableCell>
                    {/* Table cells ignore max-width: limit the content instead. */}
                    <span className="flex max-w-[45vw] min-w-0 items-center gap-2 sm:max-w-md">
                      <CategoryIcon icon={category.icon} color={category.color} />
                      <span dir="auto" title={category.name} className="truncate font-medium">
                        {category.name}
                      </span>
                    </span>
                  </TableCell>
                  <TableCell>
                    {category.device_count > 0 ? (
                      <Link
                        to={`/devices?category=${encodeURIComponent(category.id)}`}
                        className="hover:text-primary hover:underline"
                      >
                        {devicesText(category.device_count)}
                      </Link>
                    ) : (
                      <span className="text-muted-foreground">none</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`Edit ${category.name}`}
                        onClick={() => {
                          setEditing(category)
                        }}
                      >
                        <Pencil />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`Delete ${category.name}`}
                        onClick={() => {
                          setDeleteError(null)
                          setToDelete(category)
                        }}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <CategoryDialog open={creating} onOpenChange={setCreating} />
      <CategoryDialog
        category={editing ?? undefined}
        open={editing !== null}
        onOpenChange={(open) => {
          if (!open) setEditing(null)
        }}
      />
      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => {
          if (!open) setToDelete(null)
        }}
        title={
          <>
            Delete <span dir="auto">{toDelete?.name}</span>?
          </>
        }
        description={
          toDelete && toDelete.device_count > 0
            ? `${devicesText(toDelete.device_count)} will have no category. The devices themselves are kept.`
            : 'No devices use it.'
        }
        confirmLabel="Delete category"
        onConfirm={confirmDelete}
        returnFocus={() => addButton.current}
        pending={remove.isPending}
        error={deleteError}
      />
    </section>
  )
}
