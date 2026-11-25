/**
 * The map's logic, kept apart from React Flow's canvas so it can be unit-tested (jsdom cannot
 * lay out or drag the canvas): devices and links become nodes and edges, moves become
 * position saves, and straight edges run between the borders of two nodes.
 */

import type { Edge, Node, NodeChange, XYPosition } from '@xyflow/react'

import type { Category, Device, DevicePosition, Link, LinkType } from '@/api/types'
import { statusText } from '@/lib/status'

/** Fixed node size. The backend's grid (240 x 140) uses it too: keep in sync with
 * `NODE_WIDTH` / `NODE_HEIGHT` in backend/app/services/devices.py. */
export const NODE_WIDTH = 192
export const NODE_HEIGHT = 56
/** Dragging snaps to this grid; arrow keys move by one step (Shift: four). */
export const SNAP_GRID = 20
/** How far nodes can go: the backend's limit for map coordinates (`MAP_COORDINATE_LIMIT`). */
export const MAP_LIMIT = 100_000
const GRID_SPACING_X = 240
const GRID_SPACING_Y = 140

export const LINK_TYPES: readonly { value: LinkType; label: string }[] = [
  { value: 'ethernet', label: 'Ethernet' },
  { value: 'wifi', label: 'Wi-Fi' },
  { value: 'vpn', label: 'VPN' },
  { value: 'other', label: 'Other' },
]

export function linkTypeLabel(type: LinkType): string {
  return LINK_TYPES.find((entry) => entry.value === type)?.label ?? type
}

export interface DeviceNodeData extends Record<string, unknown> {
  device: Device
  category: Category | undefined
}
export type DeviceNode = Node<DeviceNodeData, 'device'>

export interface LinkEdgeData extends Record<string, unknown> {
  link: Link
}
export type LinkEdge = Edge<LinkEdgeData, 'link'>

function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function hasPosition(device: Device): boolean {
  return isFiniteNumber(device.map_x) && isFiniteNumber(device.map_y)
}

/**
 * Nodes for the devices. The backend gives every new device a free grid cell; a device
 * without a position (none today; M8's import might) is shown in a row below the others and
 * saved once it is moved.
 *
 * `previous` keeps what only the canvas knows:
 * - which nodes are selected;
 * - the position of a node being dragged, or moved with the arrow keys and not saved yet
 *   (`pending`), so new server data does not pull it back;
 * - React Flow's measurements (`measured`): without them it drops the handles and draws no
 *   edge until it has measured the nodes again (every line flickered after each save).
 *
 * A node whose device, category and position did not change stays the same object, so
 * React Flow does not render it again.
 */
export function toNodes(
  devices: readonly Device[],
  categories: readonly Category[],
  previous: readonly DeviceNode[] = [],
  pending: ReadonlyMap<string, XYPosition> = new Map(),
): DeviceNode[] {
  const categoryById = new Map(categories.map((category) => [category.id, category]))
  const previousById = new Map(previous.map((node) => [node.id, node]))

  const placed = devices.filter(hasPosition)
  const bottom = Math.max(0, ...placed.map((device) => (device.map_y ?? 0) + NODE_HEIGHT))
  let unplaced = 0

  return devices.map((device) => {
    const old = previousById.get(device.id)
    let position: XYPosition
    if (old?.dragging) {
      position = old.position
    } else if (pending.has(device.id)) {
      position = pending.get(device.id) ?? old?.position ?? { x: 0, y: 0 }
    } else if (hasPosition(device)) {
      position = { x: device.map_x ?? 0, y: device.map_y ?? 0 }
    } else {
      const column = unplaced++
      position = {
        x: column * GRID_SPACING_X,
        y: placed.length > 0 ? bottom + GRID_SPACING_Y - NODE_HEIGHT : 0,
      }
    }
    const category = device.category_id ? categoryById.get(device.category_id) : undefined
    if (
      old?.data.device === device &&
      old.data.category === category &&
      old.position.x === position.x &&
      old.position.y === position.y
    ) {
      return old
    }
    const node: DeviceNode = {
      id: device.id,
      type: 'device',
      position,
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
      data: { device, category },
      ariaLabel: nodeLabel(device, category),
      selected: old?.selected ?? false,
    }
    if (old?.dragging) node.dragging = true
    if (old?.measured) node.measured = old.measured
    return node
  })
}

/** What a screen reader hears for a node: name, category, address and status. */
export function nodeLabel(device: Device, category: Category | undefined): string {
  return [
    device.name,
    category?.name,
    device.ip_address ?? device.hostname,
    device.status === 'off' ? null : statusText(device, ', '),
  ]
    .filter(Boolean)
    .join(', ')
}

/** Edges for the links whose two devices are both on the map. */
export function toEdges(links: readonly Link[], devices: readonly Device[]): LinkEdge[] {
  const nameById = new Map(devices.map((device) => [device.id, device.name]))
  return links.flatMap((link) => {
    const a = nameById.get(link.device_a_id)
    const b = nameById.get(link.device_b_id)
    if (a === undefined || b === undefined) return []
    const label = link.label ? ` (${link.label})` : ''
    return [
      {
        id: link.id,
        type: 'link',
        source: link.device_a_id,
        target: link.device_b_id,
        data: { link },
        ariaLabel: `${linkTypeLabel(link.link_type)} link between ${a} and ${b}${label}`,
      },
    ]
  })
}

/** Links that touch a device, with the device at the other end. */
export function linksOf(
  deviceId: string,
  links: readonly Link[],
  devices: readonly Device[],
): { link: Link; other: Device }[] {
  const byId = new Map(devices.map((device) => [device.id, device]))
  return links
    .flatMap((link) => {
      const otherId =
        link.device_a_id === deviceId
          ? link.device_b_id
          : link.device_b_id === deviceId
            ? link.device_a_id
            : null
      const other = otherId === null ? undefined : byId.get(otherId)
      return other ? [{ link, other }] : []
    })
    .sort((x, y) => x.other.name.localeCompare(y.other.name))
}

/** Whether two devices may get a new link: not to itself, not twice (links have no
 * direction). The backend decides; this only stops the canvas from offering it. */
export function canLink(a: string, b: string, links: readonly Link[]): boolean {
  if (a === b) return false
  const [low, high] = a < b ? [a, b] : [b, a]
  return !links.some((link) => link.device_a_id === low && link.device_b_id === high)
}

/**
 * Finished moves among React Flow's node changes: position changes with `dragging: false`.
 * A drag reports those once when it ends (only if something moved); each arrow-key press
 * reports one.
 */
export function finishedMoves(changes: readonly NodeChange[]): Map<string, XYPosition> {
  const moves = new Map<string, XYPosition>()
  for (const change of changes) {
    if (change.type === 'position' && change.dragging === false && change.position) {
      moves.set(change.id, change.position)
    }
  }
  return moves
}

/** The request body for moves (ids in a stable order). */
export function toPositions(moves: ReadonlyMap<string, XYPosition>): DevicePosition[] {
  return [...moves.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([device_id, position]) => ({ device_id, map_x: position.x, map_y: position.y }))
}

/** Devices with the saved positions applied (for the query cache, before the answer). */
export function withPositions(
  devices: readonly Device[],
  positions: readonly DevicePosition[],
): Device[] {
  const byId = new Map(positions.map((position) => [position.device_id, position]))
  return devices.map((device) => {
    const position = byId.get(device.id)
    return position ? { ...device, map_x: position.map_x, map_y: position.map_y } : device
  })
}

export interface Rect {
  x: number
  y: number
  width: number
  height: number
}

/** Where the line from the center of `rect` toward `point` leaves the rectangle. */
export function borderPoint(rect: Rect, point: XYPosition): XYPosition {
  const cx = rect.x + rect.width / 2
  const cy = rect.y + rect.height / 2
  const dx = point.x - cx
  const dy = point.y - cy
  if (dx === 0 && dy === 0) return { x: cx, y: cy }
  // Scale the direction until it reaches the nearer of the vertical or horizontal border.
  const scale = Math.min(
    dx === 0 ? Infinity : rect.width / 2 / Math.abs(dx),
    dy === 0 ? Infinity : rect.height / 2 / Math.abs(dy),
  )
  return { x: cx + dx * scale, y: cy + dy * scale }
}

/** A straight edge between two nodes: from border to border, along the line through their
 * centers. Links have no direction, so no handle decides where an edge starts. */
export function edgeEndpoints(a: Rect, b: Rect): { source: XYPosition; target: XYPosition } {
  const centerA = { x: a.x + a.width / 2, y: a.y + a.height / 2 }
  const centerB = { x: b.x + b.width / 2, y: b.y + b.height / 2 }
  return { source: borderPoint(a, centerB), target: borderPoint(b, centerA) }
}
