// Global UI state: vehicles, settings, the selected vehicle and period, and toasts.

import { computed, reactive } from 'vue'
import { api, type Settings, type Vehicle } from './api'
import { isoDate } from './format'

export type Preset = 'this_month' | 'last_month' | 'this_year' | 'last_year' | 'last_12m' | 'all' | 'custom'

export const PRESETS: { value: Preset; label: string }[] = [
  { value: 'this_month', label: 'This month' },
  { value: 'last_month', label: 'Last month' },
  { value: 'this_year', label: 'This year' },
  { value: 'last_year', label: 'Last year' },
  { value: 'last_12m', label: 'Last 12 months' },
  { value: 'all', label: 'All time' },
  { value: 'custom', label: 'Custom…' },
]

interface Toast {
  id: number
  message: string
  actionLabel?: string
  action?: () => void
}

export const state = reactive({
  vehicles: [] as Vehicle[],
  settings: null as Settings | null,
  vehicleId: '', // '' = all vehicles
  preset: 'this_month' as Preset,
  customFrom: '',
  customTo: '',
  toasts: [] as Toast[],
  reviewCount: 0,
  loadError: '',
})

export const activeVehicles = computed(() => state.vehicles.filter((v) => !v.archived_at))

export function vehicleName(id: string): string {
  return state.vehicles.find((v) => v.id === id)?.name ?? '—'
}

export function periodRange(): { from: string; to: string } {
  const today = new Date()
  const y = today.getFullYear()
  const m = today.getMonth()
  switch (state.preset) {
    case 'last_month':
      return { from: isoDate(new Date(y, m - 1, 1)), to: isoDate(new Date(y, m, 0)) }
    case 'this_year':
      return { from: isoDate(new Date(y, 0, 1)), to: isoDate(today) }
    case 'last_year':
      return { from: isoDate(new Date(y - 1, 0, 1)), to: isoDate(new Date(y - 1, 11, 31)) }
    case 'last_12m':
      return { from: isoDate(new Date(y - 1, m, today.getDate() + 1)), to: isoDate(today) }
    case 'all': {
      const starts = state.vehicles.map((v) => v.start_date).sort()
      return { from: starts[0] ?? isoDate(today), to: isoDate(today) }
    }
    case 'custom':
      return { from: state.customFrom || isoDate(today), to: state.customTo || isoDate(today) }
    default:
      return { from: isoDate(new Date(y, m, 1)), to: isoDate(today) }
  }
}

export async function loadVehicles(): Promise<void> {
  state.vehicles = (await api.list<Vehicle>('vehicles')).items
  if (state.vehicleId && !state.vehicles.some((v) => v.id === state.vehicleId)) state.vehicleId = ''
}

export async function loadReviewCount(): Promise<void> {
  state.reviewCount = (await api.reviewItems()).total
}

export async function loadSettings(): Promise<void> {
  state.settings = await api.settings()
}

let toastId = 0

export function toast(message: string, actionLabel?: string, action?: () => void): void {
  const id = ++toastId
  state.toasts.push({ id, message, actionLabel, action })
  setTimeout(() => dismissToast(id), action ? 10000 : 5000)
}

export function dismissToast(id: number): void {
  const index = state.toasts.findIndex((t) => t.id === id)
  if (index >= 0) state.toasts.splice(index, 1)
}
