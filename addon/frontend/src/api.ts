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
  kwh_per_pct: number | null
  color: string | null
  note: string | null
  archived_at: string | null
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
  note: string | null
}

export interface Expense extends RecordBase {
  vehicle_id: string
  category: string
  amount: number
  date: string
  recurrence: 'monthly' | 'quarterly' | 'yearly' | null
  end_date: string | null
  note: string | null
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
  exportUrl: (resource: Resource, params?: Params) => url(`/export/${resource}.csv`, params),
}
