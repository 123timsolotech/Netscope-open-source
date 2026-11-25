import {
  BaseEdge,
  EdgeLabelRenderer,
  getStraightPath,
  useInternalNode,
  type EdgeProps,
  type InternalNode,
} from '@xyflow/react'

import { useMapActions } from '@/components/topology/mapActions'
import { edgeEndpoints, NODE_HEIGHT, NODE_WIDTH, type LinkEdge, type Rect } from '@/lib/topology'
import { cn } from '@/lib/utils'

function rectOf(node: InternalNode): Rect {
  return {
    ...node.internals.positionAbsolute,
    width: node.measured.width ?? node.width ?? NODE_WIDTH,
    height: node.measured.height ?? node.height ?? NODE_HEIGHT,
  }
}

/** A link: a straight line between the borders of its two devices (links have no
 * direction), drawn by type, with its label in the middle. Click it to edit. */
export function LinkEdgeView({ id, source, target, data, selected }: EdgeProps<LinkEdge>) {
  const actions = useMapActions()
  const a = useInternalNode(source)
  const b = useInternalNode(target)
  if (!a || !b || !data) return null

  const ends = edgeEndpoints(rectOf(a), rectOf(b))
  const [path, labelX, labelY] = getStraightPath({
    sourceX: ends.source.x,
    sourceY: ends.source.y,
    targetX: ends.target.x,
    targetY: ends.target.y,
  })
  const { link } = data
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        interactionWidth={16}
        className={cn('map-link', `map-link-${link.link_type}`, selected && 'map-link-selected')}
      />
      {link.label && (
        <EdgeLabelRenderer>
          <button
            type="button"
            dir="auto"
            aria-label={`Edit link: ${link.label}`}
            title={link.label}
            onClick={() => {
              actions.editLink(link)
            }}
            style={{
              transform: `translate(-50%, -50%) translate(${String(labelX)}px, ${String(labelY)}px)`,
            }}
            className="nodrag nopan pointer-events-auto absolute max-w-36 truncate rounded border bg-background px-1.5 py-0.5 text-xs text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          >
            {link.label}
          </button>
        </EdgeLabelRenderer>
      )}
    </>
  )
}
