// Display labels for the enum values the API uses. Labels are getters, so they
// follow the interface language wherever an option list is shown.

import { t, type Key } from './i18n'

export interface Option {
  value: string | null
  readonly label: string
}

function options(group: string, values: (string | null)[], keyOf: (v: string | null) => string = (v) => String(v)): Option[] {
  return values.map((value) => ({
    value,
    get label() {
      return t(`common.labels.${group}.${keyOf(value)}` as Key)
    },
  }))
}

function record(group: string, keys: string[]): Record<string, string> {
  const result: Record<string, string> = {}
  for (const key of keys) {
    Object.defineProperty(result, key, { enumerable: true, get: () => t(`common.labels.${group}.${key}` as Key) })
  }
  return result
}

export const VEHICLE_TYPES = options('vehicleTypes', ['ICE', 'PHEV', 'BEV'])
export const FUEL_TYPES = options('fuelTypes', ['petrol', 'diesel', 'lpg', 'none'])
export const MAINTENANCE_CATEGORIES = options('maintenanceCategories',
  ['service', 'inspection', 'tyres', 'repair', 'battery', 'cleaning', 'other'])
export const EXPENSE_CATEGORIES = options('expenseCategories',
  ['insurance', 'road_tax', 'parking', 'tolls', 'car_wash', 'fine', 'accessories', 'lease', 'subscription', 'other'])
export const RECURRENCES = options('recurrences', [null, 'monthly', 'quarterly', 'yearly'], (v) => v ?? 'once')
export const SPLITS = options('splits', [null, 'equal', 'km', 'percent'], (v) => v ?? 'single')
export const CHARGE_KINDS = options('chargeKinds', ['home', 'public', 'manual'])
export const PRICE_MODES = options('priceModes', ['per_kwh', 'total', 'free', 'samples'])
export const TRIP_KINDS = options('tripKinds', ['one_way', 'round_trip'])
export const FACTOR_MODES = options('factorModes', ['manual', 'learned', 'default'])
export const DUE_STATUSES = record('dueStatuses', ['ok', 'soon', 'overdue', 'unknown'])
export const IMPORT_RESOURCES = options('importResources',
  ['refuels', 'maintenance', 'odometer-readings', 'expenses'], (v) => (v === 'odometer-readings' ? 'odometerReadings' : String(v)))
export const IMPORT_FIELDS = record('importFields', ['ts', 'date', 'litres', 'price_per_l', 'total', 'odometer_km',
  'full_tank', 'station', 'note', 'category', 'description', 'garage', 'cost', 'amount'])
export const REVIEW_REASONS = record('reviewReasons', ['refuel_price', 'public_charge_price', 'possible_engine_charge',
  'charge_without_vehicle', 'rejected_event'])
export const LANGUAGES = options('languages', ['auto', 'en', 'nl'])

export function label(options: Option[], value: string | null | undefined): string {
  return options.find((o) => o.value === (value ?? null))?.label ?? value ?? '—'
}
