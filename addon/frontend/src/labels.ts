// Display labels for the enum values the API uses.

export interface Option {
  value: string | null
  label: string
}

export const VEHICLE_TYPES: Option[] = [
  { value: 'ICE', label: 'Fuel (ICE)' },
  { value: 'PHEV', label: 'Plug-in hybrid (PHEV)' },
  { value: 'BEV', label: 'Electric (BEV)' },
]

export const FUEL_TYPES: Option[] = [
  { value: 'petrol', label: 'Petrol' },
  { value: 'diesel', label: 'Diesel' },
  { value: 'lpg', label: 'LPG' },
  { value: 'none', label: 'None' },
]

export const MAINTENANCE_CATEGORIES: Option[] = [
  { value: 'service', label: 'Service' },
  { value: 'inspection', label: 'Inspection (APK)' },
  { value: 'tyres', label: 'Tyres' },
  { value: 'repair', label: 'Repair' },
  { value: 'battery', label: 'Battery' },
  { value: 'cleaning', label: 'Cleaning' },
  { value: 'other', label: 'Other' },
]

export const EXPENSE_CATEGORIES: Option[] = [
  { value: 'insurance', label: 'Insurance' },
  { value: 'road_tax', label: 'Road tax (MRB)' },
  { value: 'parking', label: 'Parking' },
  { value: 'tolls', label: 'Tolls' },
  { value: 'car_wash', label: 'Car wash' },
  { value: 'fine', label: 'Fine' },
  { value: 'accessories', label: 'Accessories' },
  { value: 'lease', label: 'Lease' },
  { value: 'subscription', label: 'Subscription' },
  { value: 'other', label: 'Other' },
]

export const RECURRENCES: Option[] = [
  { value: null, label: 'One-off' },
  { value: 'monthly', label: 'Every month' },
  { value: 'quarterly', label: 'Every quarter' },
  { value: 'yearly', label: 'Every year' },
]

export function label(options: Option[], value: string | null | undefined): string {
  return options.find((o) => o.value === (value ?? null))?.label ?? value ?? '—'
}
