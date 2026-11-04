import { t } from '../i18n'
import type { Option } from '../labels'
import { activeVehicles, state } from '../store'

export interface Field {
  key: string
  label: string
  type: 'text' | 'number' | 'date' | 'datetime' | 'select' | 'checkbox' | 'textarea' | 'color'
  options?: Option[]
  required?: boolean
  step?: string
  min?: number
  hint?: string
  placeholder?: string
  half?: boolean
  show?: (values: Record<string, unknown>) => boolean
}

export function vehicleField(): Field {
  return {
    key: 'vehicle_id',
    label: t('common.app.filters.vehicle'),
    type: 'select',
    required: true,
    options: activeVehicles.value.map((v) => ({ value: v.id, label: v.name })),
  }
}

/** The vehicle a new record defaults to: the selected one, or the only one. */
export function defaultVehicleId(): string | null {
  if (state.vehicleId) return state.vehicleId
  return activeVehicles.value.length === 1 ? activeVehicles.value[0].id : null
}
