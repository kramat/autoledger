<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, type OdometerReading, type Refuel } from '../api'
import DataTable, { type Column } from '../components/DataTable.vue'
import { clip } from '../attachments'
import RecordDialog from '../components/RecordDialog.vue'
import { defaultVehicleId, vehicleField, type Field } from '../components/fields'
import { fmtDateTime, km, money, nowLocalInput, num } from '../format'
import { activeVehicles, state, vehicleName } from '../store'
import { useCrud } from '../useCrud'

const tab = ref<'refuels' | 'odometer'>('refuels')
const params = () => ({ vehicle_id: state.vehicleId || undefined })
const allVehicles = computed(() => !state.vehicleId)

const refuels = useCrud<Refuel>('refuels', params, { noun: 'Refuel' })
const readings = useCrud<OdometerReading>('odometer-readings', params, { noun: 'Odometer reading' })

const refuelColumns = computed<Column<Refuel>[]>(() => [
  { key: 'ts', label: 'Date', value: (r) => fmtDateTime(r.ts) },
  ...(allVehicles.value ? [{ key: 'vehicle', label: 'Vehicle', value: (r: Refuel) => vehicleName(r.vehicle_id) }] : []),
  { key: 'odometer', label: 'Odometer', num: true, value: (r) => km(r.odometer_km) },
  { key: 'litres', label: 'Litres', num: true, value: (r) => num(r.litres, 2) },
  { key: 'price', label: 'Price / L', num: true, value: (r) => money(r.price_per_l, 3) },
  { key: 'total', label: 'Total', num: true, value: (r) => money(r.total) },
  { key: 'full', label: 'Tank', value: (r) => (r.full_tank ? 'Full' : 'Partial') },
  { key: 'cons', label: 'L/100 km', num: true, value: (r) => num(r.l_per_100km, 2) },
  { key: 'station', label: 'Station', wrap: true, value: (r) => r.station ?? '' },
  { key: 'receipt', label: 'Receipt', value: clip },
])

const readingColumns = computed<Column<OdometerReading>[]>(() => [
  { key: 'ts', label: 'Date', value: (r) => fmtDateTime(r.ts) },
  ...(allVehicles.value
    ? [{ key: 'vehicle', label: 'Vehicle', value: (r: OdometerReading) => vehicleName(r.vehicle_id) }]
    : []),
  { key: 'odometer', label: 'Odometer', num: true, value: (r) => km(r.odometer_km) },
  { key: 'note', label: 'Note', wrap: true, value: (r) => r.note ?? '' },
])

const refuelFields = computed<Field[]>(() => [
  vehicleField(),
  { key: 'ts', label: 'Date and time', type: 'datetime', required: true },
  { key: 'odometer_km', label: 'Odometer (km)', type: 'number', min: 0, half: true, hint: 'Needed for L/100 km' },
  { key: 'full_tank', label: 'Filled the tank completely', type: 'checkbox', half: true },
  { key: 'litres', label: 'Litres', type: 'number', min: 0, half: true },
  { key: 'total', label: 'Total paid', type: 'number', min: 0, half: true },
  {
    key: 'price_per_l',
    label: 'Price per litre',
    type: 'number',
    min: 0,
    hint: 'Fill in two of litres, total and price per litre. The third is calculated.',
  },
  { key: 'station', label: 'Station', type: 'text' },
  { key: 'note', label: 'Note', type: 'textarea' },
])

const readingFields = computed<Field[]>(() => [
  vehicleField(),
  { key: 'ts', label: 'Date and time', type: 'datetime', required: true },
  { key: 'odometer_km', label: 'Odometer (km)', type: 'number', min: 0, required: true },
  { key: 'note', label: 'Note', type: 'textarea' },
])

const totals = computed(() => ({
  litres: refuels.items.value.reduce((sum, r) => sum + r.litres, 0),
  cost: refuels.items.value.reduce((sum, r) => sum + r.total, 0),
}))

function add(): void {
  const base = { vehicle_id: defaultVehicleId(), ts: new Date(nowLocalInput()).toISOString() }
  if (tab.value === 'refuels') refuels.openCreate({ ...base, full_tank: true })
  else readings.openCreate(base)
}

function exportUrl(): string {
  return api.exportUrl(tab.value === 'refuels' ? 'refuels' : 'odometer-readings', params())
}
</script>

<template>
  <div>
    <div class="page-head">
      <div class="segmented" role="group" aria-label="Show">
        <button :class="{ on: tab === 'refuels' }" :aria-pressed="tab === 'refuels'" @click="tab = 'refuels'">Refuels</button>
        <button :class="{ on: tab === 'odometer' }" :aria-pressed="tab === 'odometer'" @click="tab = 'odometer'">Odometer readings</button>
      </div>
      <div class="actions">
        <a :href="exportUrl()" download><button>Export CSV</button></a>
        <button class="primary" :disabled="!activeVehicles.length" @click="add">
          {{ tab === 'refuels' ? 'Add refuel' : 'Add reading' }}
        </button>
      </div>
    </div>

    <template v-if="tab === 'refuels'">
      <p v-if="refuels.error.value" class="notice error">{{ refuels.error.value }}</p>
      <DataTable :columns="refuelColumns" :rows="refuels.items.value" :loading="refuels.loading.value"
        empty="No refuels yet." @edit="refuels.openEdit" @delete="refuels.remove">
        <template v-if="refuels.items.value.length" #foot>
          <tr>
            <td :colspan="allVehicles ? 3 : 2">
              {{ refuels.items.value.length }} {{ refuels.items.value.length === 1 ? 'refuel' : 'refuels' }}
            </td>
            <td class="num">{{ num(totals.litres, 1) }}</td>
            <td></td>
            <td class="num">{{ money(totals.cost) }}</td>
            <td colspan="4"></td>
          </tr>
        </template>
      </DataTable>
      <p class="small muted">
        L/100 km is calculated from one full tank to the next, including partial refuels in between.
      </p>
    </template>

    <template v-else>
      <p v-if="readings.error.value" class="notice error">{{ readings.error.value }}</p>
      <DataTable :columns="readingColumns" :rows="readings.items.value" :loading="readings.loading.value"
        empty="No odometer readings yet. Refuels and maintenance with an odometer value count too."
        @edit="readings.openEdit" @delete="readings.remove" />
    </template>

    <RecordDialog v-if="refuels.dialog.value" :title="refuels.dialog.value.mode === 'create' ? 'Add refuel' : 'Edit refuel'"
      :fields="refuelFields" :initial="refuels.dialog.value.initial" :mode="refuels.dialog.value.mode"
      :save="refuels.save" attachments="refuels" @changed="refuels.load" @close="refuels.dialog.value = null" />
    <RecordDialog v-if="readings.dialog.value"
      :title="readings.dialog.value.mode === 'create' ? 'Add odometer reading' : 'Edit odometer reading'"
      :fields="readingFields" :initial="readings.dialog.value.initial" :mode="readings.dialog.value.mode"
      :save="readings.save" @close="readings.dialog.value = null" />
  </div>
</template>
