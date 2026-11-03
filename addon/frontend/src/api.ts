// Typed client for the add-on REST API (docs/api.md).
// All URLs are relative so they resolve under the Ingress path.

const BASE = 'api/v1'

export interface RecordBase {
  id: string
  created_at: string
  updated_at: string
  version: number
  deleted_at: string | null
}

export type VehicleType = 'ICE' | 'PHEV' | 'BEV'
export type FuelType = 'petrol' | 'diesel' | 'lpg' | 'none'

export interface Vehicle extends RecordBase {
  name: string
  plate: string | null
  make: string | null
  model: string | null
  year: number | null
  type: VehicleType
  fuel_type: FuelType
  tank_l: number | null
  battery_usable_kwh: number | null
  tracking: 'manual' | 'collector'
  start_odometer_km: number
  start_date: string
  purchase_price: number | null
  purchase_date: string | null
  resale_estimate: number | null
  resale_date: string | null
  depreciation_enabled: boolean
  kwh_per_pct: number | null
  color: string | null
  note: string | null
  archived_at: string | null
}

export type AttachmentResource = 'refuels' | 'maintenance' | 'expenses'

export interface Attachment {
  id: string
  resource: AttachmentResource
  record_id: string
  filename: string
  mime_type: string
  size: number
  created_at: string
}

export interface Refuel extends RecordBase {
  vehicle_id: string
  ts: string
  odometer_km: number | null
  litres: number
  price_per_l: number
  total: number
  full_tank: boolean
  station: string | null
  note: string | null
  source: string
  status: string
  interval_km: number | null
  l_per_100km: number | null
  attachments: Attachment[]
}

export type PriceMode = 'samples' | 'per_kwh' | 'total' | 'free'

export interface Charge extends RecordBase {
  vehicle_id: string | null
  kind: 'home' | 'public' | 'manual'
  start_ts: string
  end_ts: string | null
  energy_kwh: number
  price_mode: PriceMode
  price_per_kwh: number | null
  price_total: number | null
  session_fee: number | null
  soc_start: number | null
  soc_end: number | null
  address: string | null
  provider: string | null
  note: string | null
  source: string
  status: string
  locked_fields: string[]
  session_key: string | null
  charger_name: string | null
  is_open: boolean
  energy_estimated: boolean
  auto_cost: number | null
  cost: number
  avg_price: number | null
}

export interface TripCosting {
  energy_kwh: number
  kwh_per_pct: number | null
  factor_mode: 'manual' | 'learned' | 'default' | null
  kwh_price: number | null
  electricity_cost: number
  fuel_l_measured: number
  fuel_l_provisional: number
  fuel_l: number
  fuel_reconciled: boolean
  l_price: number | null
  fuel_cost: number
  cost: number
  notes: string[]
}

export interface Trip extends RecordBase {
  vehicle_id: string
  start_ts: string
  start_ts_estimated: boolean
  end_ts: string
  start_lat: number | null
  start_lon: number | null
  start_address: string | null
  start_zone: string | null
  end_lat: number | null
  end_lon: number | null
  end_address: string | null
  end_zone: string | null
  kind: 'one_way' | 'round_trip'
  odometer_start: number | null
  odometer_end: number | null
  distance_km: number
  distance_source: 'trip_meter' | 'odometer' | 'manual'
  battery_start_pct: number | null
  battery_end_pct: number | null
  battery_used_pct: number | null
  charged_kwh: number
  energy_kwh: number | null
  fuel_start_l: number | null
  fuel_end_l: number | null
  fuel_l: number
  origin: { merged_from?: string[]; split_from?: string }
  note: string | null
  source: string
  status: string
  locked_fields: string[]
  costing: TripCosting | null
}

export interface IdleRecord extends RecordBase {
  vehicle_id: string
  start_ts: string
  end_ts: string
  zone: string | null
  battery_start_pct: number | null
  battery_end_pct: number | null
  battery_used_pct: number | null
  energy_kwh: number | null
  fuel_l: number
  note: string | null
  source: string
  costing: TripCosting | null
}

export interface ReviewItem extends RecordBase {
  vehicle_id: string | null
  record_type: 'refuel' | 'charge' | null
  record_id: string | null
  reason: string
  details: Record<string, unknown>
  resolved_at: string | null
  record: (Refuel & Charge) | null
}

export interface OdometerReading extends RecordBase {
  vehicle_id: string
  ts: string
  odometer_km: number
  note: string | null
}

export interface MaintenanceRecord extends RecordBase {
  vehicle_id: string
  date: string
  odometer_km: number | null
  category: string
  description: string
  garage: string | null
  cost: number
  schedule_id: string | null
  note: string | null
  attachments: Attachment[]
}

export type DueStatus = 'ok' | 'soon' | 'overdue' | 'unknown'

export interface ScheduleDue {
  schedule_id: string
  name: string
  status: DueStatus
  last_done_date: string | null
  last_done_km: number | null
  last_record_id: string | null
  due_date: string | null
  due_km: number | null
  km_left: number | null
  estimated_date: string | null
  reason: 'date' | 'km' | null
  days_left: number | null
}

export interface MaintenanceSchedule extends RecordBase {
  vehicle_id: string
  name: string
  category: string | null
  interval_months: number | null
  interval_km: number | null
  last_done_date: string | null
  last_done_km: number | null
  remind_before_days: number
  remind_before_km: number
  active: boolean
  note: string | null
  due: ScheduleDue | null
}

export interface CarService {
  days_to_service: number | null
  distance_to_service: number | null
  reported_at: string
  odometer_km: number | null
  due_date: string | null
  due_km: number | null
}

export interface VehicleDue {
  vehicle_id: string
  vehicle_name: string
  odometer_km: number | null
  km_per_day: number | null
  car_service: CarService | null
  items: (ScheduleDue & { category: string | null; interval_months: number | null; interval_km: number | null })[]
}

export interface Expense extends RecordBase {
  vehicle_id: string
  category: string
  amount: number
  date: string
  recurrence: 'monthly' | 'quarterly' | 'yearly' | null
  end_date: string | null
  note: string | null
  attachments: Attachment[]
}

export interface Settings {
  currency: string
  electricity_price: number
  public_charge_price: number
  fuel_prices: { petrol: number; diesel: number; lpg: number }
}

export interface Totals {
  km: number
  fuel_l: number
  fuel_cost: number
  electricity_kwh: number
  electricity_cost: number
  maintenance_cost: number
  other_cost: number
  depreciation_cost: number
  energy_cost: number
  total_cost: number
  energy_cost_per_km: number | null
  total_cost_per_km: number | null
  fuel_l_per_100km: number | null
  refuel_count: number
  charge_count: number
  maintenance_count: number
  distance_known_until: string | null
  trip_count: number
  trip_km: number
  trip_kwh: number
  trip_fuel_l: number
  trip_cost: number
  kwh_per_100km: number | null
  electric_share: number | null
  idle_kwh: number
  idle_fuel_l: number
  idle_cost: number
}

export interface Efficiency {
  kwh_per_pct: number
  mode: 'manual' | 'learned' | 'default'
  sessions: string[]
  learnable_sessions: number
  learned: number | null
  default: number | null
}

export interface MonthTotals extends Totals {
  month: string
}

export interface VehicleSummary {
  vehicle: Vehicle
  period: Totals
  rolling_12m: Totals
  odometer_km: number | null
  odometer_ts: string | null
  odometer_points_ignored: number
  last_refuel: Refuel | null
  open_charge: Charge | null
  last_charge: Charge | null
  last_trip: Trip | null
  efficiency: Efficiency | null
  trips_since: string | null
  maintenance: ScheduleDue[]
  next_maintenance: ScheduleDue | null
  car_service: CarService | null
  monthly: MonthTotals[]
}

export interface Summary {
  from: string
  to: string
  currency: string
  review_count: number
  vehicles: VehicleSummary[]
  combined: { period: Totals; monthly: MonthTotals[] }
}

export type ReportGroup = 'month' | 'quarter' | 'year' | 'none'

export interface PerYear {
  km: number | null
  total_cost: number | null
  energy_cost: number | null
  maintenance_cost: number | null
  other_cost: number | null
  depreciation_cost: number | null
}

export interface GroupTotals extends Totals {
  label: string
  from: string
  to: string
}

export interface PeriodReport {
  from: string
  to: string
  group: ReportGroup
  days: number
  currency: string
  vehicles: { vehicle: Vehicle; total: Totals; per_year: PerYear; groups: GroupTotals[] }[]
  combined: { total: Totals; per_year: PerYear; groups: GroupTotals[] }
}

export interface TrendMonth {
  month: string
  km: number
  energy_cost_per_km: number | null
  total_cost_per_km: number | null
  kwh_per_100km: number | null
  fuel_l_per_100km: number | null
  electric_share: number | null
  total_cost: number
}

export interface SeasonFigures {
  months: number
  km: number
  trip_km: number
  kwh_per_100km: number | null
  fuel_l_per_100km: number | null
  energy_cost_per_km: number | null
  electric_share: number | null
  idle_kwh: number
}

export interface Trends {
  currency: string
  vehicles: {
    vehicle: Vehicle
    since: string
    monthly: TrendMonth[]
    seasons: Record<'winter' | 'spring' | 'summer' | 'autumn', SeasonFigures>
  }[]
}

export type ImportResource = 'refuels' | 'maintenance' | 'odometer-readings' | 'expenses'

export interface ImportRequest {
  resource: ImportResource
  vehicle_id: string
  content: string
  mapping?: Record<string, string> | null
  delimiter?: string | null
  decimal?: '.' | ',' | null
  date_order?: 'dmy' | 'mdy' | 'ymd' | null
}

export interface ImportPreview {
  columns: string[]
  delimiter: string
  decimal: '.' | ','
  date_order: 'dmy' | 'mdy' | 'ymd'
  mapping: Record<string, string>
  fields: { name: string; required: boolean }[]
  rows: { line: number; status: 'ok' | 'error' | 'duplicate'; error: string | null; values: Record<string, unknown> }[]
  counts: { ok: number; error: number; duplicate: number }
  total_rows: number
  created: number
}

export interface RestoreResult {
  mode: 'empty' | 'merge'
  tables: Record<string, { inserted: number; skipped: number }>
  files?: { written: number; skipped: number }
}

export interface Info {
  name: string
  version: string
  api_version: number
  currency: string
  timezone: string
  last_ingest_at: string | null
}

export interface Page<T> {
  items: T[]
  total: number
}

export type Resource =
  | 'vehicles'
  | 'refuels'
  | 'odometer-readings'
  | 'charges'
  | 'maintenance'
  | 'expenses'
  | 'trips'
  | 'idle-records'
  | 'maintenance-schedules'

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public fields: Record<string, string> = {},
  ) {
    super(message)
  }
}

type Params = Record<string, string | number | boolean | null | undefined>

function url(path: string, params?: Params): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  }
  const qs = query.toString()
  return `${BASE}${path}${qs ? `?${qs}` : ''}`
}

async function request<T>(method: string, path: string, body?: unknown, params?: Params): Promise<T> {
  const response = await fetch(url(path, params), {
    method,
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (response.status === 204) return undefined as T
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(data?.error?.message ?? response.statusText, response.status, data?.error?.fields ?? {})
  }
  return data as T
}

export const api = {
  list: <T>(resource: Resource, params?: Params) => request<Page<T>>('GET', `/${resource}`, undefined, params),
  create: <T>(resource: Resource, body: object) => request<T>('POST', `/${resource}`, body),
  update: <T>(resource: Resource, id: string, body: object) => request<T>('PATCH', `/${resource}/${id}`, body),
  remove: (resource: Resource, id: string) => request<void>('DELETE', `/${resource}/${id}`),
  restore: <T>(resource: Resource, id: string) => request<T>('POST', `/${resource}/${id}/restore`),
  splitTrip: (id: string, body: { at_km: number; at_ts: string; address?: string | null }) =>
    request<Trip[]>('POST', `/trips/${id}/split`, body),
  mergeTrips: (ids: [string, string]) => request<Trip>('POST', '/trips/merge', { ids }),
  reviewItems: () => request<Page<ReviewItem>>('GET', '/review-items'),
  resolve: (id: string, action: 'update' | 'accept' | 'delete' | 'dismiss', values: object = {}) =>
    request<ReviewItem>('POST', `/review-items/${id}/resolve`, { action, values }),
  summary: (params: Params) => request<Summary>('GET', '/summary', undefined, params),
  info: () => request<Info>('GET', '/info'),
  settings: () => request<Settings>('GET', '/settings'),
  saveSettings: (settings: Settings) => request<Settings>('PUT', '/settings', settings),
  token: () => request<{ token: string }>('GET', '/settings/token'),
  regenerateToken: () => request<{ token: string }>('POST', '/settings/token/regenerate'),
  exportUrl: (resource: Resource, params?: Params, format: 'csv' | 'xlsx' = 'csv') =>
    url(`/export/${resource}.${format}`, params),
  recordsWorkbookUrl: () => url('/export/records.xlsx'),
  maintenanceDue: (params?: Params) => request<{ vehicles: VehicleDue[] }>('GET', '/maintenance-schedules/due', undefined, params),
  reportPeriod: (params: Params) => request<PeriodReport>('GET', '/reports/period', undefined, params),
  reportTrends: (params: Params) => request<Trends>('GET', '/reports/trends', undefined, params),
  reportExportUrl: (format: 'csv' | 'xlsx', params: Params) => url(`/reports/period.${format}`, params),
  backupUrl: (attachments = false) => url('/backup', { attachments: attachments || undefined }),
  restoreBackup: (data: unknown, mode: 'empty' | 'merge') => request<RestoreResult>('POST', '/restore', data, { mode }),
  importCsv: (body: ImportRequest, commit = false) =>
    request<ImportPreview>('POST', '/import/csv', body, { commit: commit || undefined }),
  attachments: (resource: AttachmentResource, recordId: string) =>
    request<Attachment[]>('GET', '/attachments', undefined, { resource, record_id: recordId }),
  uploadAttachment,
  removeAttachment: (id: string) => request<void>('DELETE', `/attachments/${id}`),
  restoreAttachment: (id: string) => request<Attachment>('POST', `/attachments/${id}/restore`),
  attachmentUrl: (id: string, download = false) => url(`/attachments/${id}/file`, { download: download || undefined }),
}

/** The file is the request body (no multipart); its type goes in Content-Type. */
async function uploadAttachment(resource: AttachmentResource, recordId: string, file: Blob, filename: string): Promise<Attachment> {
  const response = await fetch(url('/attachments', { resource, record_id: recordId, filename }), {
    method: 'POST',
    headers: { 'Content-Type': file.type || 'application/octet-stream' },
    body: file,
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(data?.error?.message ?? response.statusText, response.status)
  return data as Attachment
}
