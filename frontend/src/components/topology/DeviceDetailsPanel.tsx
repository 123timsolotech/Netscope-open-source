import { Pencil, Plus, Trash2, X } from 'lucide-react'
import type { ReactNode, Ref } from 'react'
import { Link as RouterLink } from 'react-router'

import type { Category, Device, Link } from '@/api/types'
import { CategoryIcon } from '@/components/CategoryIcon'
import type { DeviceFormLocationState } from '@/components/devices/DeviceForm'
import { DeviceStatusSummary } from '@/components/DeviceStatusSummary'
import { LinkSwatch } from '@/components/topology/LinkDialog'
import { Button } from '@/components/ui/button'
import { linkTypeLabel } from '@/lib/topology'

interface DeviceDetailsPanelProps {
  device: Device
  category: Category | undefined
  links: { link: Link; other: Device }[]
  onClose: () => void
  onShowDevice: (id: string) => void
  onAddLink: () => void
  onEditLink: (link: Link) => void
  onDeleteLink: (link: Link) => void
  headingRef?: Ref<HTMLHeadingElement>
}

/**
 * Details of the selected device, beside the map (below it on a phone), taking room from the
 * map rather than covering it: clicking another device shows that one. Its links can be edited here, which is
 * also the keyboard's way to every link.
 */
export function DeviceDetailsPanel({
  device,
  category,
  links,
  onClose,
  onShowDevice,
  onAddLink,
  onEditLink,
  onDeleteLink,
  headingRef,
}: DeviceDetailsPanelProps) {
  const editState: DeviceFormLocationState = { returnTo: '/topology' }
  return (
    <aside
      aria-labelledby="map-details-title"
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.stopPropagation()
          onClose()
        }
      }}
      className="max-h-[45%] shrink-0 overflow-y-auto border-t bg-card p-4 md:max-h-none md:w-80 md:border-t-0 md:border-l"
    >
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted">
          <CategoryIcon icon={category?.icon} color={category?.color} className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <h2
            id="map-details-title"
            ref={headingRef}
            tabIndex={-1}
            dir="auto"
            className="text-lg leading-tight font-semibold [overflow-wrap:anywhere] outline-none"
          >
            {device.name}
          </h2>
          <p dir="auto" className="text-sm text-muted-foreground">
            {category?.name ?? 'No category'}
          </p>
        </div>
        <Button variant="ghost" size="icon" aria-label="Close details" onClick={onClose}>
          <X />
        </Button>
      </div>

      <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
        <dt className="text-muted-foreground">Status</dt>
        <dd>
          <DeviceStatusSummary device={device} />
        </dd>
        <Detail label="IP address" mono value={device.ip_address} />
        <Detail label="Hostname" mono value={device.hostname} />
        <Detail label="MAC" mono value={device.mac_address} />
        <Detail label="Vendor" value={device.vendor} />
        <Detail label="Role" value={device.role} />
        <Detail label="Location" value={device.location} />
      </dl>

      {device.description && (
        <p dir="auto" className="mt-3 text-sm whitespace-pre-wrap [overflow-wrap:anywhere]">
          {device.description}
        </p>
      )}

      <Section title={`Services (${String(device.services.length)})`}>
        {device.services.length === 0 ? (
          <p className="text-sm text-muted-foreground">No services.</p>
        ) : (
          <ul className="grid gap-1 text-sm">
            {device.services.map((service) => (
              <li key={service.id} className="flex min-w-0 gap-2">
                <span className="shrink-0 font-mono text-muted-foreground">
                  {service.port}/{service.protocol}
                </span>
                <span dir="auto" className="min-w-0 [overflow-wrap:anywhere]">
                  {service.name}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title={`Links (${String(links.length)})`}>
        {links.length === 0 ? (
          <p className="text-sm text-muted-foreground">Not linked to any device.</p>
        ) : (
          <ul className="grid gap-1">
            {links.map(({ link, other }) => (
              <li key={link.id} className="flex min-w-0 items-center gap-1 text-sm">
                <LinkSwatch type={link.link_type} />
                <span className="sr-only">{linkTypeLabel(link.link_type)} to</span>
                <button
                  type="button"
                  dir="auto"
                  title={other.name}
                  onClick={() => {
                    onShowDevice(other.id)
                  }}
                  className="min-w-0 truncate rounded px-1 text-left underline-offset-2 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {other.name}
                </button>
                {link.label && (
                  <span
                    dir="auto"
                    title={link.label}
                    className="min-w-0 truncate text-xs text-muted-foreground"
                  >
                    {link.label}
                  </span>
                )}
                <span className="ml-auto flex shrink-0">
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Edit link to ${other.name}`}
                    onClick={() => {
                      onEditLink(link)
                    }}
                  >
                    <Pencil />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Delete link to ${other.name}`}
                    onClick={() => {
                      onDeleteLink(link)
                    }}
                  >
                    <Trash2 />
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <div className="mt-5 flex flex-wrap gap-2">
        <Button variant="outline" onClick={onAddLink}>
          <Plus aria-hidden="true" />
          Add link
        </Button>
        <Button asChild>
          <RouterLink to={`/devices/${device.id}`} state={editState}>
            <Pencil aria-hidden="true" />
            Edit device
          </RouterLink>
        </Button>
      </div>
    </aside>
  )
}

function Detail({ label, value, mono }: { label: string; value: string | null; mono?: boolean }) {
  if (!value) return null
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd
        dir="auto"
        className={mono ? 'font-mono [overflow-wrap:anywhere]' : '[overflow-wrap:anywhere]'}
      >
        {value}
      </dd>
    </>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-5">
      <h3 className="mb-2 text-sm font-medium">{title}</h3>
      {children}
    </section>
  )
}
