import '@/styles/topology.css'

import {
  Background,
  BackgroundVariant,
  ConnectionLineType,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  applyNodeChanges,
  useReactFlow,
  type Connection,
  type EdgeTypes,
  type IsValidConnection,
  type NodeChange,
  type NodeTypes,
  type Viewport,
  type XYPosition,
} from '@xyflow/react'
import { Plus } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link as RouterLink } from 'react-router'
import { toast } from 'sonner'

import { isApiError } from '@/api/client'
import type { Category, Device, Link } from '@/api/types'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { EmptyState, ErrorState, LoadingState, RefreshNotice } from '@/components/PageStates'
import { DeviceDetailsPanel } from '@/components/topology/DeviceDetailsPanel'
import { DeviceNodeView } from '@/components/topology/DeviceNode'
import { LinkDialog, LinkSwatch, type LinkDialogTarget } from '@/components/topology/LinkDialog'
import { LinkEdgeView } from '@/components/topology/LinkEdge'
import { MapActionsContext, type MapActions } from '@/components/topology/mapActions'
import { Button } from '@/components/ui/button'
import { useCategories } from '@/hooks/useCategories'
import { useDevices, useSavePositions } from '@/hooks/useDevices'
import { useDeleteLink, useLinks } from '@/hooks/useLinks'
import {
  canLink,
  finishedMoves,
  LINK_TYPES,
  linksOf,
  NODE_HEIGHT,
  NODE_WIDTH,
  MAP_LIMIT,
  SNAP_GRID,
  toEdges,
  toNodes,
  toPositions,
  type DeviceNode,
  type LinkEdge,
} from '@/lib/topology'

const nodeTypes: NodeTypes = { device: DeviceNodeView }
const edgeTypes: EdgeTypes = { link: LinkEdgeView }
/** Arrow-key moves are saved this long after the last key press (a drag at once). */
const KEYBOARD_SAVE_DELAY_MS = 500

/**
 * Zoom and pan, kept while the app stays open (coming back from "Edit device" keeps the view);
 * a reload or a new tab starts fitted to every device. Nothing is stored in the browser.
 */
let rememberedViewport: Viewport | null = null

const NODE_DESCRIPTION =
  'Press Enter to select a device and show its details after the map (Tab past the map to reach them). Arrow keys move a selected device. Escape clears the selection.'

/** Screen-reader texts: no Delete key here, edges are reached through the details panel. */
const ariaLabelConfig = {
  // React Flow 12.12 reads these two keys the wrong way round (keyboardDisabled while the
  // keyboard is on), so both get the full text.
  'node.a11yDescription.default': NODE_DESCRIPTION,
  'node.a11yDescription.keyboardDisabled': NODE_DESCRIPTION,
  // React Flow passes the position before the move: say only the direction.
  'node.a11yDescription.ariaLiveMessage': ({ direction }: { direction: string }) =>
    `Moved ${direction}.`,
  'edge.a11yDescription.default': 'Links are listed in the details of each device.',
}

function nodeElement(id: string): HTMLElement | null {
  return document.querySelector<HTMLElement>(`.react-flow__node[data-id="${CSS.escape(id)}"]`)
}

/** The topology map (M5). Loaded lazily: React Flow is only downloaded for this page. */
export function TopologyPage() {
  const devices = useDevices()
  const categories = useCategories()
  const links = useLinks()

  let content
  if (devices.isPending || categories.isPending || links.isPending) {
    content = <LoadingState />
  } else if (
    // An error page only when nothing was loaded: a failed poll keeps the map (RefreshNotice).
    devices.data === undefined ||
    categories.data === undefined ||
    links.data === undefined
  ) {
    content = (
      <ErrorState
        error={devices.error ?? categories.error ?? links.error}
        onRetry={() => {
          void devices.refetch()
          void categories.refetch()
          void links.refetch()
        }}
      />
    )
  } else if (devices.data.length === 0) {
    content = (
      <EmptyState
        title="No devices yet."
        description="Add a device and it appears here, ready to be linked to others."
        action={
          <Button asChild>
            <RouterLink to="/devices/new" state={{ returnTo: '/topology' }}>
              Add device
            </RouterLink>
          </Button>
        }
      />
    )
  } else {
    content = (
      <ReactFlowProvider>
        <TopologyMap devices={devices.data} categories={categories.data} links={links.data} />
      </ReactFlowProvider>
    )
  }

  return (
    <div className="flex h-[calc(100svh-5.5rem)] min-h-96 flex-col gap-4 md:h-[calc(100svh-4rem)]">
      <header>
        <h1 className="text-2xl font-semibold">Topology</h1>
        <p className="hidden text-sm text-muted-foreground sm:block">
          Drag devices to arrange them. Drag the dot on a device to another to link them.
        </p>
      </header>
      {(devices.isError || categories.isError || links.isError) &&
        devices.data !== undefined &&
        categories.data !== undefined &&
        links.data !== undefined && (
          <RefreshNotice error={devices.error ?? categories.error ?? links.error} />
        )}
      {content}
    </div>
  )
}

interface TopologyMapProps {
  devices: Device[]
  categories: Category[]
  links: Link[]
}

function TopologyMap({ devices, categories, links }: TopologyMapProps) {
  const flow = useReactFlow<DeviceNode>()
  const [nodes, setNodes] = useState(() => toNodes(devices, categories))
  // Moves not saved yet (arrow keys wait for the last press).
  const pendingMoves = useRef(new Map<string, XYPosition>())
  // New data from the server: rebuild the nodes, keeping the selection, any node being
  // dragged and moves not saved yet (adjusting state during render, as React recommends
  // instead of an effect).
  const [source, setSource] = useState({ devices, categories })
  if (source.devices !== devices || source.categories !== categories) {
    setSource({ devices, categories })
    setNodes((previous) => toNodes(devices, categories, previous, pendingMoves.current))
  }
  const edges = useMemo(() => toEdges(links, devices), [links, devices])

  const [linkDialog, setLinkDialog] = useState<LinkDialogTarget | null>(null)
  const [linkToDelete, setLinkToDelete] = useState<Link | null>(null)
  const deleteLink = useDeleteLink()
  const detailsHeading = useRef<HTMLHeadingElement>(null)
  const addLinkButton = useRef<HTMLButtonElement>(null)

  const savePositions = useSavePositions({
    onError: (error) => {
      if (isApiError(error, 422) && error.issues.some((i) => i.type === 'device_not_found')) {
        // Deleted in another tab or window while this map still showed it.
        toast.error('A moved device no longer exists.', {
          description:
            'It was deleted elsewhere, so these moves were not saved. The map now shows the current devices.',
        })
        return
      }
      toast.error(`Could not save the new positions: ${error.message}`, {
        description: 'The map shows the positions as last saved.',
      })
    },
  })
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const flushMoves = useCallback(() => {
    if (saveTimer.current !== null) clearTimeout(saveTimer.current)
    saveTimer.current = null
    if (pendingMoves.current.size === 0) return
    const positions = toPositions(pendingMoves.current)
    pendingMoves.current = new Map()
    savePositions(positions)
  }, [savePositions])

  // Leaving the page within the keyboard delay still saves the last moves.
  useEffect(() => flushMoves, [flushMoves])

  const onNodesChange = useCallback(
    (changes: NodeChange<DeviceNode>[]) => {
      setNodes((current) => applyNodeChanges(changes, current))
      const moves = finishedMoves(changes)
      if (moves.size === 0) return
      for (const [id, position] of moves) pendingMoves.current.set(id, position)
      // A drag end saves at once (onNodeDragStop); arrow keys wait for the last press.
      if (saveTimer.current !== null) clearTimeout(saveTimer.current)
      saveTimer.current = setTimeout(flushMoves, KEYBOARD_SAVE_DELAY_MS)
    },
    [flushMoves],
  )

  const selected = nodes.filter((node) => node.selected)
  const detailsNode = selected.length === 1 ? selected[0] : undefined
  const detailsDevice = detailsNode?.data.device

  const selectOnly = useCallback((id: string | null) => {
    setNodes((current) =>
      current.map((node) =>
        node.selected === (node.id === id) ? node : { ...node, selected: node.id === id },
      ),
    )
  }, [])

  // The panel takes room from the map: keep the selected device in view.
  const mapArea = useRef<HTMLDivElement>(null)
  const detailsId = detailsNode?.id
  useEffect(() => {
    if (!detailsId) return
    const frame = requestAnimationFrame(() => {
      const area = mapArea.current?.getBoundingClientRect()
      const box = nodeElement(detailsId)?.getBoundingClientRect()
      const node = flow.getNode(detailsId)
      if (!area || !box || !node) return
      const outside =
        box.left < area.left ||
        box.right > area.right ||
        box.top < area.top ||
        box.bottom > area.bottom
      if (outside) {
        void flow.setCenter(node.position.x + NODE_WIDTH / 2, node.position.y + NODE_HEIGHT / 2, {
          zoom: flow.getZoom(),
          duration: 200,
        })
      }
    })
    return () => {
      cancelAnimationFrame(frame)
    }
  }, [detailsId, flow])

  const showDevice = (id: string) => {
    selectOnly(id)
    const node = flow.getNode(id)
    if (node) {
      void flow.setCenter(node.position.x + NODE_WIDTH / 2, node.position.y + NODE_HEIGHT / 2, {
        zoom: flow.getZoom(),
        duration: 300,
      })
    }
    // The panel shows the other device: move focus to its heading for keyboard users.
    requestAnimationFrame(() => detailsHeading.current?.focus())
  }

  const closeDetails = () => {
    const id = detailsNode?.id
    selectOnly(null)
    // Back to the node on the map, so keyboard users keep their place.
    if (id) {
      requestAnimationFrame(() => {
        nodeElement(id)?.focus()
      })
    }
  }

  const actions = useMemo<MapActions>(
    () => ({
      editLink: (link) => {
        setLinkDialog({ kind: 'edit', link })
      },
    }),
    [],
  )

  const isValidConnection: IsValidConnection = useCallback(
    (connection) => canLink(connection.source, connection.target, links),
    [links],
  )

  const onConnect = useCallback((connection: Connection) => {
    // Asks for the type and label before anything is saved.
    setLinkDialog({ kind: 'create', deviceA: connection.source, deviceB: connection.target })
  }, [])

  const confirmDelete = () => {
    if (!linkToDelete) return
    const done = (message: string) => {
      toast.success(message)
      setLinkToDelete(null)
      deleteLink.reset()
    }
    deleteLink.mutate(linkToDelete.id, {
      onSuccess: () => {
        done('Deleted the link.')
      },
      onError: (error) => {
        // Deleted meanwhile (another tab): it is gone either way.
        if (isApiError(error, 404)) done('The link was already deleted.')
      },
    })
  }

  const linkName = (link: Link) => {
    const name = (id: string) => devices.find((device) => device.id === id)?.name ?? 'a device'
    return `${name(link.device_a_id)} – ${name(link.device_b_id)}`
  }

  return (
    <MapActionsContext value={actions}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ul aria-label="Link types" className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {LINK_TYPES.map((type) => (
            <li key={type.value} className="flex items-center gap-1.5 text-muted-foreground">
              <LinkSwatch type={type.value} />
              {type.label}
            </li>
          ))}
        </ul>
        <Button
          ref={addLinkButton}
          variant="outline"
          onClick={() => {
            setLinkDialog({ kind: 'create' })
          }}
        >
          <Plus aria-hidden="true" />
          Add link
        </Button>
      </div>

      {/* The details panel sits beside the map (below it on a phone) and takes room from it,
          so it never covers a device, the zoom buttons or the attribution. */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border bg-background md:flex-row">
        <div
          ref={mapArea}
          className="relative min-h-40 min-w-0 flex-1"
          // Escape on a focused node clears the selection but keeps focus on the node
          // (React Flow would blur it, leaving focus on the page body).
          onKeyDownCapture={(event) => {
            if (
              event.key === 'Escape' &&
              event.target instanceof HTMLElement &&
              event.target.classList.contains('react-flow__node')
            ) {
              event.stopPropagation()
              selectOnly(null)
            }
          }}
        >
          <ReactFlow<DeviceNode, LinkEdge>
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            onNodesChange={onNodesChange}
            onNodeDragStop={flushMoves}
            onSelectionDragStop={flushMoves}
            onConnect={onConnect}
            isValidConnection={isValidConnection}
            onEdgeClick={(_event, edge) => {
              if (edge.data) setLinkDialog({ kind: 'edit', link: edge.data.link })
            }}
            onMoveEnd={(_event, viewport) => {
              rememberedViewport = viewport
            }}
            defaultViewport={rememberedViewport ?? undefined}
            fitView={rememberedViewport === null}
            fitViewOptions={{ padding: 0.15, maxZoom: 1 }}
            minZoom={0.2}
            maxZoom={2}
            snapToGrid
            snapGrid={[SNAP_GRID, SNAP_GRID]}
            // A click or tap that wobbles a little is still a click, not a move.
            nodeDragThreshold={4}
            nodeClickDistance={4}
            // The backend limits a node's top-left corner; the extent holds the whole box.
            nodeExtent={[
              [-MAP_LIMIT, -MAP_LIMIT],
              [MAP_LIMIT + NODE_WIDTH, MAP_LIMIT + NODE_HEIGHT],
            ]}
            selectNodesOnDrag={false}
            // Nothing is deleted from the keyboard: links are deleted with a confirmation.
            deleteKeyCode={null}
            edgesFocusable={false}
            connectionLineType={ConnectionLineType.Straight}
            colorMode="dark"
            ariaLabelConfig={ariaLabelConfig}
          >
            <Background variant={BackgroundVariant.Dots} gap={SNAP_GRID} size={1} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>

        {detailsDevice && (
          <DeviceDetailsPanel
            key={detailsDevice.id}
            device={detailsDevice}
            category={detailsNode.data.category}
            links={linksOf(detailsDevice.id, links, devices)}
            headingRef={detailsHeading}
            onClose={closeDetails}
            onShowDevice={showDevice}
            onAddLink={() => {
              setLinkDialog({ kind: 'create', deviceA: detailsDevice.id })
            }}
            onEditLink={(link) => {
              setLinkDialog({ kind: 'edit', link })
            }}
            onDeleteLink={setLinkToDelete}
          />
        )}
      </div>
      <p role="status" className="sr-only">
        {detailsDevice ? `${detailsDevice.name}: details shown after the map.` : ''}
      </p>

      <LinkDialog
        target={linkDialog}
        // Opened by clicking a line, there is no button to return to.
        returnFocus={() => addLinkButton.current}
        devices={devices}
        onOpenChange={(open) => {
          if (!open) setLinkDialog(null)
        }}
        onDelete={(link) => {
          setLinkDialog(null)
          setLinkToDelete(link)
        }}
      />

      <ConfirmDialog
        open={linkToDelete !== null}
        onOpenChange={(open) => {
          if (!open) {
            setLinkToDelete(null)
            deleteLink.reset()
          }
        }}
        title="Delete this link?"
        description={
          linkToDelete ? (
            <>
              <span dir="auto">{linkName(linkToDelete)}</span>. The devices stay; only the line
              between them is removed.
            </>
          ) : null
        }
        confirmLabel="Delete link"
        onConfirm={confirmDelete}
        // Opened from the edit dialog, whose button is gone by then.
        returnFocus={() => addLinkButton.current}
        pending={deleteLink.isPending}
        error={deleteLink.error?.message ?? null}
      />
    </MapActionsContext>
  )
}
