<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type Vehicle } from '../api'
import DataTable, { type Column } from '../components/DataTable.vue'
import RecordDialog from '../components/RecordDialog.vue'
import type { Field } from '../components/fields'
import { fmtDate, isoDate, km, num } from '../format'
import { FUEL_TYPES, label, VEHICLE_TYPES } from '../labels'
import { loadVehicles, toast } from '../store'
import { useTheme } from '../theme'
import { useCrud } from '../useCrud'

const route = useRoute()
const router = useRouter()
const theme = useTheme()
const crud = useCrud<Vehicle>('vehicles', () => ({}), { noun: 'Vehicle', afterChange: loadVehicles })

function capacity(v: Vehicle): string {
  const parts = []
  if (v.tank_l) parts.push(`${num(v.tank_l)} L`)
  if (v.battery_usable_kwh) parts.push(`${num(v.battery_usable_kwh, 1)} kWh`)
  return parts.join(' · ') || '—'
}

const columns: Column<Vehicle>[] = [
  { key: 'name', label: 'Name', value: (v) => v.name + (v.archived_at ? ' (archived)' : '') },
  { key: 'type', label: 'Type', value: (v) => label(VEHICLE_TYPES, v.type) },
  { key: 'fuel', label: 'Fuel', value: (v) => label(FUEL_TYPES, v.fuel_type) },
  { key: 'plate', label: 'Plate', value: (v) => v.plate ?? '' },
  { key: 'capacity', label: 'Tank / battery', value: capacity },
  { key: 'start', label: 'Tracking from', value: (v) => `${km(v.start_odometer_km)} on ${fmtDate(v.start_date)}` },
]

const hasEngine = (values: Record<string, unknown>) => values.type !== 'BEV'
const hasBattery = (values: Record<string, unknown>) => values.type !== 'ICE'

const fields: Field[] = [
  { key: 'name', label: 'Name', type: 'text', required: true, placeholder: 'e.g. VW Up' },
  { key: 'make', label: 'Make', type: 'text', half: true },
  { key: 'model', label: 'Model', type: 'text', half: true },
  { key: 'year', label: 'Year', type: 'number', step: '1', half: true },
  { key: 'plate', label: 'Licence plate', type: 'text', half: true },
  { key: 'type', label: 'Type', type: 'select', options: VEHICLE_TYPES, required: true, half: true },
  { key: 'fuel_type', label: 'Fuel', type: 'select', options: FUEL_TYPES.filter((f) => f.value !== 'none'),
    half: true, show: hasEngine },
  { key: 'tank_l', label: 'Tank size (L)', type: 'number', min: 0, half: true, show: hasEngine },
  { key: 'battery_usable_kwh', label: 'Usable battery (kWh)', type: 'number', min: 0, half: true, show: hasBattery },
  { key: 'start_date', label: 'Tracking starts on', type: 'date', required: true, half: true,
    hint: 'The earliest date you have data for' },
  { key: 'start_odometer_km', label: 'Odometer on that date (km)', type: 'number', min: 0, required: true, half: true },
  { key: 'purchase_date', label: 'Purchase date', type: 'date', half: true },
  { key: 'purchase_price', label: 'Purchase price', type: 'number', min: 0, half: true },
  { key: 'color', label: 'Chart colour', type: 'color', half: true },
  { key: 'note', label: 'Note', type: 'textarea' },
]

function add(): void {
  crud.openCreate({
    type: 'ICE',
    fuel_type: 'petrol',
    start_date: isoDate(new Date()),
    color: theme.value.series[crud.items.value.length % 4],
  })
}

async function saveVehicle(data: Record<string, unknown>): Promise<void> {
  // An electric car has no fuel; the field is hidden, so send it explicitly.
  if (data.type === 'BEV') data.fuel_type = 'none'
  else if (data.type && crud.dialog.value?.initial.fuel_type === 'none' && !data.fuel_type) data.fuel_type = 'petrol'
  await crud.save(data)
}

async function toggleArchive(v: Vehicle): Promise<void> {
  await api.update('vehicles', v.id, { archived: !v.archived_at })
  await loadVehicles()
  await crud.load()
  toast(v.archived_at ? `${v.name} restored` : `${v.name} archived`)
}

onMounted(() => {
  if (route.query.new === '1') {
    add()
    const { new: _ignored, ...rest } = route.query
    router.replace({ query: rest })
  }
})

const archiveAction = {
  label: (v: Vehicle) => (v.archived_at ? 'Unarchive' : 'Archive'),
  run: toggleArchive,
}

const archivedCount = computed(() => crud.items.value.filter((v) => v.archived_at).length)
</script>

<template>
  <div>
    <div class="page-head">
      <h2>Vehicles</h2>
      <div class="actions">
        <button class="primary" @click="add">Add vehicle</button>
      </div>
    </div>
    <p v-if="crud.error.value" class="notice error">{{ crud.error.value }}</p>
    <DataTable :columns="columns" :rows="crud.items.value" :loading="crud.loading.value" empty="No vehicles yet."
      :extra="archiveAction" @edit="crud.openEdit" @delete="crud.remove" />
    <p class="small muted">
      Archived vehicles disappear from the vehicle picker but stay in reports.
      <template v-if="archivedCount"> {{ archivedCount }} archived.</template>
    </p>
    <RecordDialog v-if="crud.dialog.value" :title="crud.dialog.value.mode === 'create' ? 'Add vehicle' : 'Edit vehicle'"
      :fields="fields" :initial="crud.dialog.value.initial" :mode="crud.dialog.value.mode" :save="saveVehicle"
      @close="crud.dialog.value = null" />
  </div>
</template>
