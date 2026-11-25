import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef } from 'react'

import {
  createDevice,
  deleteDevice,
  getDevice,
  listDevices,
  savePositions,
  updateDevice,
} from '@/api/devices'
import type { Device, DevicePosition, DeviceSaved, DeviceUpdate } from '@/api/types'
import { POLL_INTERVAL_MS, queryKeys, WAITING_POLL_INTERVAL_MS } from '@/hooks/queryClient'
import { withPositions } from '@/lib/topology'

/**
 * Map moves sent but not confirmed yet, per query client: device id -> the position and the
 * save that carries it. Laid over every device list that arrives meanwhile, so a poll answered
 * just before a save is stored cannot pull a node back (M6; decision M5.7 covers moves not
 * sent yet).
 */
const unconfirmed = new WeakMap<
  QueryClient,
  Map<string, { position: DevicePosition; seq: number }>
>()

function unconfirmedMoves(client: QueryClient) {
  let moves = unconfirmed.get(client)
  if (!moves) {
    moves = new Map()
    unconfirmed.set(client, moves)
  }
  return moves
}

function withUnconfirmedMoves(client: QueryClient, devices: Device[]): Device[] {
  const moves = unconfirmedMoves(client)
  if (moves.size === 0) return devices
  return withPositions(
    devices,
    [...moves.values()].map((move) => move.position),
  )
}

/** Every 5 s while a check has no result at all yet (just turned on or changed), else 30 s. */
function pollInterval(devices: readonly Device[]): number {
  return devices.some((device) => device.status === 'waiting' && device.last_checked_at === null)
    ? WAITING_POLL_INTERVAL_MS
    : POLL_INTERVAL_MS
}

/** Every device, loaded again every 30 s while the tab is visible (status dots, M6); every
 * 5 s while one waits for its first result. */
export function useDevices() {
  const client = useQueryClient()
  return useQuery({
    queryKey: queryKeys.devices,
    queryFn: async ({ signal }) => withUnconfirmedMoves(client, await listDevices(signal)),
    refetchInterval: (query) => pollInterval(query.state.data ?? []),
  })
}

/** One device (the form), loaded again like the list, for its status. */
export function useDevice(id: string) {
  return useQuery({
    queryKey: queryKeys.device(id),
    queryFn: ({ signal }) => getDevice(id, signal),
    refetchInterval: (query) => pollInterval(query.state.data ? [query.state.data] : []),
  })
}

/** The list, the category counts and the dashboard change with every device write. */
function refreshLists(client: QueryClient): Promise<unknown> {
  return Promise.all([
    client.invalidateQueries({ queryKey: queryKeys.devices, exact: true }),
    client.invalidateQueries({ queryKey: queryKeys.categories }),
    client.invalidateQueries({ queryKey: queryKeys.dashboard }),
  ])
}

function rememberSaved(client: QueryClient, saved: DeviceSaved): void {
  const device: Device & { warnings?: unknown } = { ...saved }
  delete device.warnings
  client.setQueryData<Device>(queryKeys.device(device.id), device)
}

export function useCreateDevice() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: createDevice,
    onSuccess: (saved) => {
      rememberSaved(client, saved)
      return refreshLists(client)
    },
  })
}

export function useUpdateDevice() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: DeviceUpdate }) => updateDevice(id, body),
    onSuccess: (saved) => {
      rememberSaved(client, saved)
      return refreshLists(client)
    },
  })
}

export function useDeleteDevice() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: deleteDevice,
    onSuccess: (_result, id) => {
      client.removeQueries({ queryKey: queryKeys.device(id), exact: true })
      // Deleting a device deletes its links too.
      return Promise.all([
        refreshLists(client),
        client.invalidateQueries({ queryKey: queryKeys.links }),
      ])
    },
  })
}

function applyPositions(client: QueryClient, positions: DevicePosition[]): void {
  client.setQueryData<Device[]>(queryKeys.devices, (devices) =>
    devices ? withPositions(devices, positions) : devices,
  )
}

/**
 * Saves map moves (M5). Returns `save(positions)`.
 *
 * - The device list in the cache gets the new positions at once (before the request is
 *   queued), so the map never shows a node jumping back.
 * - Saves run one after another (`scope`), so an older move never lands after a newer one.
 * - When the newest save has succeeded, the list is loaded again: every earlier save is done
 *   by then, so the answer has the positions as saved.
 * - On failure, `onError` runs (the page shows a message). The list is loaded again once no
 *   newer save is queued, which puts the nodes back where the server has them.
 */
export function useSavePositions({ onError }: { onError: (error: Error) => void }) {
  const client = useQueryClient()
  const latest = useRef(0)
  const onErrorRef = useRef(onError)
  useEffect(() => {
    onErrorRef.current = onError
  })
  const { mutate } = useMutation({
    mutationFn: ({ positions }: { positions: DevicePosition[]; seq: number }) =>
      savePositions(positions),
    scope: { id: 'map-positions' },
    onSuccess: (_result, { seq }) => {
      // Stored: the server's lists have these positions from now on.
      forget(seq)
      if (seq !== latest.current) return
      return client.invalidateQueries({ queryKey: queryKeys.devices, exact: true })
    },
    onError: (error, { seq }) => {
      forget(seq)
      onErrorRef.current(error)
      // Newer saves are still queued: reloading now would pull their nodes back. The newest
      // save reloads the list when it is done (success or not).
      if (seq !== latest.current) return
      return client.invalidateQueries({ queryKey: queryKeys.devices, exact: true })
    },
  })
  /** Drops the moves this save carried, unless a newer save moved the same device again. */
  function forget(seq: number): void {
    const moves = unconfirmedMoves(client)
    for (const [id, move] of moves) if (move.seq === seq) moves.delete(id)
  }
  return useCallback(
    (positions: DevicePosition[]) => {
      if (positions.length === 0) return
      // A list request already on its way would bring the old positions back.
      void client.cancelQueries({ queryKey: queryKeys.devices, exact: true })
      applyPositions(client, positions)
      latest.current += 1
      const moves = unconfirmedMoves(client)
      for (const position of positions) {
        moves.set(position.device_id, { position, seq: latest.current })
      }
      mutate({ positions, seq: latest.current })
    },
    [client, mutate],
  )
}
