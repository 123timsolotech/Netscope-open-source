import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Trash2,
  X,
} from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router'
import { toast } from 'sonner'

import type { Category, Device } from '@/api/types'
import { CategoryIcon, CategoryLabel } from '@/components/CategoryIcon'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import type { DeviceFormLocationState } from '@/components/devices/DeviceForm'
import { EmptyState, ErrorState, LoadingState, RefreshNotice } from '@/components/PageStates'
import { StatusDot } from '@/components/StatusDot'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useCategories } from '@/hooks/useCategories'
import { useDeleteDevice, useDevices } from '@/hooks/useDevices'
import { categoryMatches, deviceMatches, searchTerms } from '@/lib/search'
import { sortDevices, type SortDirection, type SortKey } from '@/lib/sort'
import { failedCheckText, statusDescription, statusText } from '@/lib/status'
import { cn } from '@/lib/utils'

const ALL = '__all__'
const SORT_KEYS: SortKey[] = ['name', 'ip', 'category', 'status']

/** Search, filter and sort live in the URL (?q=&category=&sort=&dir=), so they survive a reload. */
function useListParams() {
  const [params, setParams] = useSearchParams()
  const query = params.get('q') ?? ''
  const category = params.get('category')
  const sortParam = params.get('sort') as SortKey | null
  const sort: SortKey = sortParam !== null && SORT_KEYS.includes(sortParam) ? sortParam : 'name'
  const direction: SortDirection = params.get('dir') === 'desc' ? 'desc' : 'asc'

  function update(changes: Record<string, string | null>) {
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        for (const [key, value] of Object.entries(changes)) {
          if (value === null || value === '') next.delete(key)
          else next.set(key, value)
        }
        return next
      },
      { replace: true },
    )
  }

  return { query, category, sort, direction, update }
}

function SortHeader({
  label,
  column,
  sort,
  direction,
  onSort,
  className,
  labelOnNarrow = true,
}: {
  label: string
  column: SortKey
  sort: SortKey
  direction: SortDirection
  onSort: (column: SortKey) => void
  className?: string
  /** False: below 1280 px only the arrow shows (the label stays for screen readers and as
   * the button's tooltip). */
  labelOnNarrow?: boolean
}) {
  const active = sort === column
  const Icon = !active ? ArrowUpDown : direction === 'asc' ? ArrowUp : ArrowDown
  return (
    <TableHead
      aria-sort={active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'}
      className={className}
    >
      <button
        type="button"
        title={labelOnNarrow ? undefined : label}
        onClick={() => {
          onSort(column)
        }}
        className="inline-flex items-center gap-1 rounded-sm font-medium outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <span className={cn(!labelOnNarrow && 'max-xl:sr-only')}>{label}</span>
        <Icon
          aria-hidden="true"
          className={cn('size-3.5', !active && 'text-muted-foreground/60')}
        />
      </button>
    </TableHead>
  )
}

function Muted({ children }: { children: React.ReactNode }) {
  return <span className="text-muted-foreground">{children}</span>
}

/** Sign and words from 1280 px on. Narrower, only the sign shows (its shape differs per
 * status), so names keep their room; the words are for screen readers and the tooltip. The
 * reason a check failed is the second line. */
function StatusCell({ device }: { device: Device }) {
  const off = device.status === 'off'
  const failed = failedCheckText(device)
  return (
    <div
      className="flex min-w-0 items-center gap-2"
      title={off ? undefined : statusDescription(device)}
    >
      <StatusDot status={device.status} />
      <div className="grid min-w-0">
        <span className={cn('whitespace-nowrap max-xl:sr-only', off && 'text-muted-foreground')}>
          {statusText(device)}
        </span>
        {failed !== null && (
          // Wide screens only, wrapped (table cells do not wrap by default); elsewhere the
          // tooltip, the form and the map's details give the reason.
          <span className="hidden text-xs whitespace-normal text-muted-foreground xl:line-clamp-2">
            {failed}
          </span>
        )}
      </div>
    </div>
  )
}

export function DevicesPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const devices = useDevices()
  const categories = useCategories()
  const remove = useDeleteDevice()
  const { query, category, sort, direction, update } = useListParams()
  const [toDelete, setToDelete] = useState<Device | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  // Focus targets after the delete dialog closes: the row's menu button, or (row deleted)
  // the search box.
  const lastActions = useRef<HTMLButtonElement | null>(null)
  const searchBox = useRef<HTMLInputElement | null>(null)
  const addDevice = useRef<HTMLAnchorElement | null>(null) // when the last device is deleted

  const categoryById = useMemo(
    () => new Map((categories.data ?? []).map((item) => [item.id, item])),
    [categories.data],
  )
  // A category id in the URL that no longer exists filters nothing.
  const categoryFilter =
    category === 'none' || (category !== null && categoryById.has(category)) ? category : null

  const visible = useMemo(() => {
    const terms = searchTerms(query)
    const matching = (devices.data ?? []).filter(
      (device) =>
        categoryMatches(device, categoryFilter) &&
        deviceMatches(
          device,
          terms,
          device.category_id === null ? undefined : categoryById.get(device.category_id),
        ),
    )
    return sortDevices(matching, sort, direction, categoryById)
  }, [devices.data, query, categoryFilter, sort, direction, categoryById])

  if (devices.isPending || categories.isPending) return <LoadingState />
  // An error page only when nothing was loaded: a failed poll keeps the list (RefreshNotice).
  if (devices.data === undefined)
    return <ErrorState error={devices.error} onRetry={() => void devices.refetch()} />
  if (categories.data === undefined)
    return <ErrorState error={categories.error} onRetry={() => void categories.refetch()} />

  const linkState: DeviceFormLocationState = { returnTo: `${location.pathname}${location.search}` }
  const total = devices.data.length
  const filtered = query.trim() !== '' || categoryFilter !== null

  function onSort(column: SortKey) {
    if (column === sort) update({ dir: direction === 'asc' ? 'desc' : null })
    else update({ sort: column === 'name' ? null : column, dir: null })
  }

  function confirmDelete() {
    if (!toDelete) return
    const device = toDelete
    setDeleteError(null)
    remove.mutate(device.id, {
      onSuccess: () => {
        toast.success(`Deleted ${device.name}.`)
        setToDelete(null)
      },
      onError: (error) => {
        setDeleteError(error.message)
      },
    })
  }

  return (
    <div className="grid gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Devices</h1>
          <p className="text-sm text-muted-foreground">
            {filtered
              ? `${String(visible.length)} of ${String(total)} ${total === 1 ? 'device' : 'devices'}`
              : `${String(total)} ${total === 1 ? 'device' : 'devices'}`}
          </p>
        </div>
        <Button asChild>
          <Link ref={addDevice} to="/devices/new" state={linkState}>
            <Plus aria-hidden="true" />
            Add device
          </Link>
        </Button>
      </header>

      {(devices.isError || categories.isError) && (
        <RefreshNotice error={devices.error ?? categories.error} />
      )}

      {total === 0 ? (
        <EmptyState
          title="No devices yet"
          description="Add your router, switches, servers and everything else on your network. NetScope does not scan; you enter each device yourself."
          action={
            <Button asChild>
              <Link to="/devices/new" state={linkState}>
                <Plus aria-hidden="true" />
                Add your first device
              </Link>
            </Button>
          }
        />
      ) : (
        <>
          {/* min-w-0: a grid item otherwise widens the page to its unbreakable content (a long
              category name in the filter made it 520 px wide at 390 px). */}
          <div className="flex min-w-0 flex-wrap gap-2" role="search">
            <div className="relative min-w-56 flex-1">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                ref={searchBox}
                type="search"
                aria-label="Search devices"
                placeholder="Search name, IP, MAC, vendor, service, port…"
                value={query}
                onChange={(event) => {
                  update({ q: event.target.value })
                }}
                className="pl-8"
                dir="auto"
              />
            </div>
            <Select
              value={categoryFilter ?? ALL}
              onValueChange={(value) => {
                update({ category: value === ALL ? null : value })
              }}
            >
              <SelectTrigger aria-label="Filter by category" className="max-w-full min-w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All categories</SelectItem>
                <SelectItem value="none">No category</SelectItem>
                <SelectSeparator />
                {categories.data.map((item: Category) => (
                  <SelectItem key={item.id} value={item.id}>
                    <CategoryIcon icon={item.icon} color={item.color} />
                    <span dir="auto" title={item.name} className="min-w-0 truncate">
                      {item.name}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {visible.length === 0 ? (
            <EmptyState
              title="No devices match"
              description="Try other words, or clear the search and the category filter."
              action={
                <Button
                  variant="outline"
                  onClick={() => {
                    update({ q: null, category: null })
                  }}
                >
                  <X aria-hidden="true" />
                  Clear filters
                </Button>
              }
            />
          ) : (
            <div className="rounded-xl border bg-card">
              <Table>
                <TableHeader>
                  <TableRow>
                    <SortHeader
                      label="Status"
                      column="status"
                      sort={sort}
                      direction={direction}
                      onSort={onSort}
                      className="w-10 xl:w-auto"
                      labelOnNarrow={false}
                    />
                    <SortHeader
                      label="Name"
                      column="name"
                      sort={sort}
                      direction={direction}
                      onSort={onSort}
                    />
                    <SortHeader
                      label="Category"
                      column="category"
                      sort={sort}
                      direction={direction}
                      onSort={onSort}
                      className="hidden sm:table-cell"
                    />
                    <SortHeader
                      label="IP address"
                      column="ip"
                      sort={sort}
                      direction={direction}
                      onSort={onSort}
                    />
                    <TableHead className="hidden xl:table-cell">MAC / vendor</TableHead>
                    <TableHead className="hidden md:table-cell">Location</TableHead>
                    <TableHead className="hidden md:table-cell">Services</TableHead>
                    <TableHead className="w-10">
                      <span className="sr-only">Actions</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visible.map((device) => {
                    const deviceCategory =
                      device.category_id === null ? undefined : categoryById.get(device.category_id)
                    const editPath = `/devices/${encodeURIComponent(device.id)}`
                    return (
                      <TableRow key={device.id}>
                        <TableCell className="max-w-44 min-[1400px]:max-w-60">
                          <StatusCell device={device} />
                        </TableCell>
                        <TableCell className="max-w-64">
                          <div className="grid">
                            <Link
                              to={editPath}
                              state={linkState}
                              dir="auto"
                              title={device.name}
                              className="truncate font-medium hover:text-primary hover:underline"
                            >
                              {device.name}
                            </Link>
                            {(device.hostname ?? device.role) && (
                              <span
                                dir="auto"
                                title={device.role ?? device.hostname ?? undefined}
                                className="truncate text-xs text-muted-foreground"
                              >
                                {device.role ?? device.hostname}
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="hidden max-w-48 sm:table-cell">
                          <CategoryLabel category={deviceCategory} />
                        </TableCell>
                        <TableCell className="font-mono text-sm">
                          {device.ip_address ?? <Muted>—</Muted>}
                        </TableCell>
                        <TableCell className="hidden max-w-56 xl:table-cell">
                          {device.mac_address ? (
                            <div className="grid">
                              <span className="font-mono text-sm">{device.mac_address}</span>
                              {device.vendor && (
                                <span
                                  dir="auto"
                                  title={device.vendor}
                                  className="truncate text-xs text-muted-foreground"
                                >
                                  {device.vendor}
                                </span>
                              )}
                            </div>
                          ) : (
                            <Muted>—</Muted>
                          )}
                        </TableCell>
                        <TableCell className="hidden max-w-48 truncate md:table-cell">
                          {device.location ? (
                            <span dir="auto" title={device.location}>
                              {device.location}
                            </span>
                          ) : (
                            <Muted>—</Muted>
                          )}
                        </TableCell>
                        <TableCell className="hidden md:table-cell">
                          {device.services.length > 0 ? (
                            <Badge
                              variant="secondary"
                              title={device.services
                                .map(
                                  (service) =>
                                    `${String(service.port)}/${service.protocol} ${service.name}`,
                                )
                                .join('\n')}
                            >
                              {device.services.length}
                            </Badge>
                          ) : (
                            <Muted>—</Muted>
                          )}
                        </TableCell>
                        <TableCell>
                          <DropdownMenu modal={false}>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                aria-label={`Actions for ${device.name}`}
                                onFocus={(event) => {
                                  lastActions.current = event.currentTarget
                                }}
                              >
                                <MoreHorizontal />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                onSelect={() => {
                                  void navigate(editPath, { state: linkState })
                                }}
                              >
                                <Pencil aria-hidden="true" />
                                Edit
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                variant="destructive"
                                onSelect={() => {
                                  setDeleteError(null)
                                  setToDelete(device)
                                }}
                              >
                                <Trash2 aria-hidden="true" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </>
      )}

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
        description="Its services, links and status history are deleted too. This cannot be undone."
        confirmLabel="Delete device"
        onConfirm={confirmDelete}
        returnFocus={() =>
          [lastActions.current, searchBox.current, addDevice.current].find(
            (element) => element?.isConnected,
          )
        }
        pending={remove.isPending}
        error={deleteError}
      />
    </div>
  )
}
