import { createContext, use } from 'react'

import type { Link } from '@/api/types'

/** What the map's nodes and edges can ask the page to do. */
export interface MapActions {
  editLink: (link: Link) => void
}

export const MapActionsContext = createContext<MapActions | null>(null)

export function useMapActions(): MapActions {
  const actions = use(MapActionsContext)
  if (!actions) throw new Error('useMapActions needs a MapActionsContext provider.')
  return actions
}
