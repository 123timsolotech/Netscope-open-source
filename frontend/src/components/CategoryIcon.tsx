import { createElement } from 'react'

import type { Category } from '@/api/types'
import { safeColor } from '@/lib/colors'
import { iconFor } from '@/lib/icons'
import { cn } from '@/lib/utils'

interface CategoryIconProps {
  icon: string | null | undefined
  color: string | null | undefined
  className?: string
}

/** The category's Lucide icon in its color (a fallback icon for names outside the set). */
export function CategoryIcon({ icon, color, className }: CategoryIconProps) {
  // createElement: the icon comes from a fixed map, it is not a component made during render.
  return createElement(iconFor(icon), {
    'aria-hidden': true,
    className: cn('size-4 shrink-0', className),
    style: { color: safeColor(color) },
  })
}

/** Icon and name, or a muted "No category". */
export function CategoryLabel({ category }: { category: Category | undefined }) {
  if (!category) return <span className="text-muted-foreground">No category</span>
  return (
    <span className="inline-flex min-w-0 items-center gap-2">
      <CategoryIcon icon={category.icon} color={category.color} />
      <span dir="auto" title={category.name} className="truncate">
        {category.name}
      </span>
    </span>
  )
}
