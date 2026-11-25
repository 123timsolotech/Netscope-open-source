import { z } from 'zod'

import type { CheckType, Device, DeviceCreate } from '@/api/types'

/**
 * Light checks only (decision M4): what the form can tell without the backend. Everything
 * else (addresses, uniqueness, check rules, lengths) is decided by the backend, and its 422
 * answer is shown next to the fields.
 */
const PORT_MESSAGE = 'Enter a port from 1 to 65535.'

export function usesCheckPort(type: CheckType): boolean {
  return type === 'tcp' || type === 'http'
}

function isPort(value: string): boolean {
  if (!/^\d{1,5}$/.test(value.trim())) return false
  const port = Number(value.trim())
  return port >= 1 && port <= 65535
}

const serviceSchema = z.object({
  port: z.string().refine(isPort, PORT_MESSAGE),
  protocol: z.enum(['tcp', 'udp']),
  name: z.string().trim().min(1, 'Enter a service name.'),
  note: z.string(),
})

export const deviceFormSchema = z
  .object({
    name: z.string().trim().min(1, 'Enter a name.'),
    hostname: z.string(),
    ip_address: z.string(),
    mac_address: z.string(),
    category_id: z.string(),
    role: z.string(),
    location: z.string(),
    description: z.string(),
    check_type: z.enum(['none', 'icmp', 'tcp', 'http']),
    check_enabled: z.boolean(),
    check_port: z.string(),
    check_scheme: z.enum(['http', 'https']),
    check_path: z.string(),
    check_verify_tls: z.boolean(),
    services: z.array(serviceSchema),
  })
  .superRefine((values, context) => {
    // Only TCP and HTTP checks use (and show) the port; a leftover value from another type
    // must not block saving (it is sent as null, see toRequestBody).
    if (
      usesCheckPort(values.check_type) &&
      values.check_port.trim() !== '' &&
      !isPort(values.check_port)
    ) {
      context.addIssue({ code: 'custom', path: ['check_port'], message: PORT_MESSAGE })
    }
  })

export type DeviceFormValues = z.infer<typeof deviceFormSchema>
export type ServiceFormValues = DeviceFormValues['services'][number]

export const EMPTY_SERVICE: ServiceFormValues = { port: '', protocol: 'tcp', name: '', note: '' }

export function toFormValues(device?: Device): DeviceFormValues {
  return {
    name: device?.name ?? '',
    hostname: device?.hostname ?? '',
    ip_address: device?.ip_address ?? '',
    mac_address: device?.mac_address ?? '',
    category_id: device?.category_id ?? '',
    role: device?.role ?? '',
    location: device?.location ?? '',
    description: device?.description ?? '',
    check_type: device?.check_type ?? 'none',
    check_enabled: device?.check_enabled ?? false,
    check_port: device?.check_port == null ? '' : String(device.check_port),
    check_scheme: device?.check_scheme ?? 'http',
    check_path: device?.check_path ?? '/',
    check_verify_tls: device?.check_verify_tls ?? false,
    services: (device?.services ?? []).map((service) => ({
      port: String(service.port),
      protocol: service.protocol,
      name: service.name,
      note: service.note ?? '',
    })),
  }
}

/** Blank optional text is sent as null, which clears it on an update. */
function optional(value: string): string | null {
  return value.trim() === '' ? null : value
}

function port(value: string): number {
  return Number(value.trim())
}

/** The check port as sent: a leftover value that is not a port is dropped for checks that do
 * not use one (decision M4). */
function checkPortValue(values: Pick<DeviceFormValues, 'check_type' | 'check_port'>) {
  return values.check_port.trim() === '' ||
    (!usesCheckPort(values.check_type) && !isPort(values.check_port))
    ? null
    : port(values.check_port)
}

export type CheckFormFields = Pick<
  DeviceFormValues,
  | 'check_type'
  | 'check_enabled'
  | 'check_port'
  | 'check_scheme'
  | 'check_path'
  | 'check_verify_tls'
  | 'ip_address'
  | 'hostname'
>

export const CHECK_FORM_FIELDS = [
  'check_type',
  'check_enabled',
  'check_port',
  'check_scheme',
  'check_path',
  'check_verify_tls',
  'ip_address',
  'hostname',
] as const satisfies readonly (keyof CheckFormFields)[]

/**
 * Whether the form still describes the device's saved check, so the saved status belongs to
 * it: the same fields the backend compares before resetting the status (M6).
 */
export function sameCheck(values: CheckFormFields, device: Device): boolean {
  const target = optional(values.ip_address) ?? optional(values.hostname)
  return (
    values.check_type === device.check_type &&
    values.check_enabled === device.check_enabled &&
    checkPortValue(values) === device.check_port &&
    values.check_scheme === device.check_scheme &&
    (values.check_path.trim() || '/') === device.check_path &&
    values.check_verify_tls === device.check_verify_tls &&
    target?.trim() === (device.ip_address ?? device.hostname ?? undefined)
  )
}

/**
 * The request body for create and for PATCH. Every field is sent (decision M4: what you see
 * is what is saved). The vendor is never sent: the backend derives it from the MAC.
 */
export function toRequestBody(values: DeviceFormValues): DeviceCreate {
  return {
    name: values.name,
    hostname: optional(values.hostname),
    ip_address: optional(values.ip_address),
    mac_address: optional(values.mac_address),
    category_id: values.category_id === '' ? null : values.category_id,
    role: optional(values.role),
    location: optional(values.location),
    description: optional(values.description),
    check_type: values.check_type,
    check_enabled: values.check_enabled,
    check_port: checkPortValue(values),
    check_scheme: values.check_scheme,
    check_path: values.check_path,
    check_verify_tls: values.check_verify_tls,
    services: values.services.map((service) => ({
      port: port(service.port),
      protocol: service.protocol,
      name: service.name,
      note: optional(service.note),
    })),
  }
}

const ALWAYS_SHOWN = new Set([
  'name',
  'hostname',
  'ip_address',
  'mac_address',
  'category_id',
  'role',
  'location',
  'description',
  'check_type',
  'check_enabled',
])
const SERVICE_FIELDS = new Set(['port', 'protocol', 'name', 'note'])

/** The check fields the form shows for a check type (the others keep their values). */
export function checkFieldsFor(type: CheckType): Set<string> {
  if (type === 'tcp') return new Set(['check_port'])
  if (type === 'http')
    return new Set(['check_port', 'check_scheme', 'check_path', 'check_verify_tls'])
  return new Set()
}

/**
 * Whether a 422 path ("services.1.port") belongs to a field the form shows right now.
 * Issues on hidden fields go into the summary instead, so none is lost.
 */
export function isVisibleDeviceField(
  path: string,
  checkType: CheckType,
  serviceCount: number,
): boolean {
  if (ALWAYS_SHOWN.has(path) || checkFieldsFor(checkType).has(path)) return true
  const match = /^services\.(\d+)\.(\w+)$/.exec(path)
  if (!match?.[1] || !match[2]) return false
  return Number(match[1]) < serviceCount && SERVICE_FIELDS.has(match[2])
}

export const CHECK_TYPE_LABELS: Record<CheckType, string> = {
  none: 'No check',
  icmp: 'Ping (ICMP)',
  tcp: 'TCP port',
  http: 'HTTP(S) request',
}
