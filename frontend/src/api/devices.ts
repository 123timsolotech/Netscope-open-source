import { api } from '@/api/client'
import type { Device, DeviceCreate, DevicePosition, DeviceSaved, DeviceUpdate } from '@/api/types'

/** Every device with its services, sorted by name (search and filters run in the browser). */
export function listDevices(signal?: AbortSignal): Promise<Device[]> {
  return api.get<Device[]>('/devices', signal)
}

export function getDevice(id: string, signal?: AbortSignal): Promise<Device> {
  return api.get<Device>(`/devices/${encodeURIComponent(id)}`, signal)
}

/** The answer carries `warnings` (shared IP or MAC); the device was saved anyway. */
export function createDevice(body: DeviceCreate): Promise<DeviceSaved> {
  return api.post<DeviceSaved>('/devices', body)
}

/** Partial update: left out = unchanged, null = cleared, `services` replaces the list. */
export function updateDevice(id: string, body: DeviceUpdate): Promise<DeviceSaved> {
  return api.patch<DeviceSaved>(`/devices/${encodeURIComponent(id)}`, body)
}

export function deleteDevice(id: string): Promise<undefined> {
  return api.delete(`/devices/${encodeURIComponent(id)}`)
}

/** Moves devices on the map: all or nothing, and not an edit (`updated_at` stays). */
export function savePositions(positions: DevicePosition[]): Promise<undefined> {
  return api.put<undefined>('/devices/positions', { positions })
}
