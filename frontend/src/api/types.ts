/**
 * API shapes. Generated from the backend's OpenAPI schema (`npm run gen:api`), except the
 * error items: the backend drops FastAPI's `input` and `url` from its 422 answers.
 */

import type { components } from '@/api/generated/schema'

type Schemas = components['schemas']

export type Category = Schemas['CategoryOut']
export type CategoryCreate = Schemas['CategoryCreate']
export type CategoryUpdate = Schemas['CategoryUpdate']

export type Device = Schemas['DeviceOut']
export type DeviceSaved = Schemas['DeviceSaved']
export type DeviceCreate = Schemas['DeviceCreate']
export type DeviceUpdate = Schemas['DeviceUpdate']
export type Service = Schemas['ServiceOut']
export type CheckType = Schemas['CheckType']
export type DeviceStatus = Schemas['DeviceStatus']
export type DevicePosition = Schemas['PositionIn']

export type Link = Schemas['LinkOut']
export type LinkCreate = Schemas['LinkCreate']
export type LinkUpdate = Schemas['LinkUpdate']
export type LinkType = Schemas['LinkType']

export type Dashboard = Schemas['DashboardOut']
export type DashboardCategory = Schemas['DashboardCategory']
export type RecentDevice = Schemas['RecentDevice']
export type DownDevice = Schemas['DownDevice']
export type StatusCounts = Schemas['StatusCounts']

export type Settings = Schemas['SettingsOut']
export type SettingsUpdate = Schemas['SettingsUpdate']

export type CurrentUser = Schemas['CurrentUser']
export type SetupStatus = Schemas['SetupStatus']
export type SetupRequest = Schemas['SetupRequest']
export type LoginRequest = Schemas['LoginRequest']
export type PasswordChange = Schemas['PasswordChange']
export type Sessions = Schemas['SessionsOut']

export type About = Schemas['AboutOut']

export type ExportFile = Schemas['ExportFile']
export type ImportMode = Schemas['ImportMode']
export type ImportCounts = Schemas['ImportCounts']
export type ImportResult = Schemas['ImportResult']

/**
 * One validation error or warning: `{"type", "loc", "msg", "ctx"?}` (decision M3.1).
 * `loc` starts with "body" for request fields, e.g. ["body", "services", 1, "port"].
 */
export interface Issue {
  type: string
  loc: (string | number)[]
  msg: string
  ctx?: Record<string, unknown>
}
