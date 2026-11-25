import { Handle, Position, useConnection, type NodeProps } from '@xyflow/react'

import { CategoryIcon } from '@/components/CategoryIcon'
import { StatusDot } from '@/components/StatusDot'
import { statusDescription } from '@/lib/status'
import type { DeviceNode } from '@/lib/topology'
import { cn } from '@/lib/utils'

/**
 * A device on the map: category icon, name and address, at a fixed size (NODE_WIDTH x
 * NODE_HEIGHT). Drag the dot on the right onto another device to link them; while a link is
 * being drawn, the whole of every other node is a drop target.
 *
 * The status sits on the icon's corner (M6), so the node keeps its size; its words are in the
 * node's label (`nodeLabel`) and tooltip. No sign when the check is off.
 */
export function DeviceNodeView({ id, data, selected }: NodeProps<DeviceNode>) {
  const connection = useConnection()
  const dropTarget = connection.inProgress && connection.fromNode.id !== id
  const { device, category } = data
  const address = device.ip_address ?? device.hostname
  return (
    <div
      title={device.status === 'off' ? undefined : statusDescription(device)}
      className={cn(
        'flex size-full items-center gap-2.5 rounded-lg border bg-card px-2.5 text-card-foreground',
        // Down also shows in the border, so it is visible when the map is zoomed out (the
        // sign and the node's name carry it in shape and words too).
        device.status === 'down' && 'border-status-down/70',
        selected && 'border-primary ring-2 ring-primary/40',
        dropTarget && 'border-dashed border-primary',
      )}
    >
      <span className="relative flex size-8 shrink-0 items-center justify-center rounded-md bg-muted">
        <CategoryIcon icon={category?.icon} color={category?.color} />
        <StatusDot
          status={device.status}
          className="absolute -right-2 -bottom-2 size-4 rounded-full bg-card ring-2 ring-card"
        />
      </span>
      <span className="grid min-w-0 flex-1">
        {/* The full name and address as tooltips (owner decision, M8); the rest of the node
            keeps the status as its tooltip. */}
        <span dir="auto" title={device.name} className="truncate text-sm leading-5 font-medium">
          {device.name}
        </span>
        {address && (
          <span
            title={address}
            className="truncate font-mono text-xs leading-4 text-muted-foreground"
          >
            {address}
          </span>
        )}
      </span>
      <Handle
        type="source"
        position={Position.Right}
        className="map-handle"
        title="Drag to another device to link them"
      />
      <Handle
        type="target"
        position={Position.Left}
        isConnectableStart={false}
        className={cn('map-drop-target', dropTarget && 'map-drop-target-active')}
      />
    </div>
  )
}
