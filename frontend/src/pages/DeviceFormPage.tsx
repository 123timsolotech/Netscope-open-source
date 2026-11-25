import { ArrowLeft } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'

import { isApiError } from '@/api/client'
import type { Category } from '@/api/types'
import { DeviceForm, type DeviceFormLocationState } from '@/components/devices/DeviceForm'
import { Notice } from '@/components/Notice'
import { EmptyState, ErrorState, LoadingState, RefreshNotice } from '@/components/PageStates'
import { Button } from '@/components/ui/button'
import { useCategories } from '@/hooks/useCategories'
import { useDevice } from '@/hooks/useDevices'
import { formReturnLabel, formReturnTarget } from '@/lib/redirect'

function PageHeader({ title, returnTo }: { title: React.ReactNode; returnTo: string }) {
  return (
    <header className="mb-6 grid gap-2">
      <Link
        to={returnTo}
        className="inline-flex items-center gap-1 justify-self-start text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        {formReturnLabel(returnTo)}
      </Link>
      <h1 className="min-w-0 text-2xl font-semibold [overflow-wrap:anywhere]">{title}</h1>
    </header>
  )
}

function EditDevice({
  id,
  categories,
  returnTo,
}: {
  id: string
  categories: Category[]
  returnTo: string
}) {
  const location = useLocation()
  const navigate = useNavigate()
  const device = useDevice(id)
  // Warnings handed over by the create page: shown once, then dropped from the history
  // entry so a reload does not show them again.
  const [initialWarnings] = useState(() => {
    const warnings = (location.state as DeviceFormLocationState | null)?.warnings
    return Array.isArray(warnings)
      ? warnings.filter((item): item is string => typeof item === 'string')
      : []
  })
  const hasWarnings = initialWarnings.length > 0
  useEffect(() => {
    if (hasWarnings)
      void navigate('.', { replace: true, state: { returnTo } satisfies DeviceFormLocationState })
  }, [hasWarnings, navigate, returnTo])

  if (device.isPending) return <LoadingState />
  // Nothing loaded: an error page. A failed poll keeps the form and its unsaved changes.
  if (device.data === undefined) {
    // 422: the address holds no valid device id at all (path validation).
    if (isApiError(device.error, 404) || isApiError(device.error, 422)) {
      return (
        <>
          <PageHeader title="Device not found" returnTo={returnTo} />
          <EmptyState
            title="This device does not exist (anymore)."
            description="It may have been deleted."
            action={
              <Button asChild variant="outline">
                <Link to={returnTo}>Back to {formReturnLabel(returnTo).toLowerCase()}</Link>
              </Button>
            }
          />
        </>
      )
    }
    return <ErrorState error={device.error} onRetry={() => void device.refetch()} />
  }

  return (
    <>
      <PageHeader title={<span dir="auto">{device.data.name}</span>} returnTo={returnTo} />
      {isApiError(device.error, 404) ? (
        <Notice
          tone="error"
          title="This device no longer exists."
          messages={['It was deleted elsewhere, so these changes cannot be saved.']}
          className="mb-6 max-w-4xl"
        />
      ) : (
        device.isError && <RefreshNotice error={device.error} className="mb-6 max-w-4xl" />
      )}
      <DeviceForm
        key={device.data.id}
        device={device.data}
        categories={categories}
        returnTo={returnTo}
        initialWarnings={initialWarnings}
      />
    </>
  )
}

/** /devices/new and /devices/:deviceId. */
export function DeviceFormPage() {
  const { deviceId } = useParams()
  const location = useLocation()
  const categories = useCategories()
  const returnTo = formReturnTarget((location.state as DeviceFormLocationState | null)?.returnTo)

  if (categories.isPending) return <LoadingState />
  if (categories.data === undefined)
    return <ErrorState error={categories.error} onRetry={() => void categories.refetch()} />

  if (deviceId === undefined) {
    return (
      <>
        <PageHeader title="Add device" returnTo={returnTo} />
        <DeviceForm key="new" categories={categories.data} returnTo={returnTo} />
      </>
    )
  }
  return (
    <EditDevice key={deviceId} id={deviceId} categories={categories.data} returnTo={returnTo} />
  )
}
