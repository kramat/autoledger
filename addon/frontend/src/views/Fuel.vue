<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, type OdometerReading, type Refuel } from '../api'
import DataTable, { type Column } from '../components/DataTable.vue'
import { clip } from '../attachments'
import RecordDialog from '../components/RecordDialog.vue'
import { defaultVehicleId, vehicleField, type Field } from '../components/fields'
import { fmtDateTime, km, money, nowLocalInput, num } from '../format'
import { t, tn } from '../i18n'
import { activeVehicles, state, vehicleName } from '../store'
import { useCrud } from '../useCrud'

const tab = ref<'refuels' | 'odometer'>('refuels')
const params = () => ({ vehicle_id: state.vehicleId || undefined })
const allVehicles = computed(() => !state.vehicleId)

const refuels = useCrud<Refuel>('refuels', params, { noun: () => t('fuel.nouns.refuel') })
const readings = useCrud<OdometerReading>('odometer-readings', params, { noun: () => t('fuel.nouns.reading') })

const refuelColumns = computed<Column<Refuel>[]>(() => [
  { key: 'ts', label: t('fuel.columns.date'), value: (r) => fmtDateTime(r.ts) },
  ...(allVehicles.value
    ? [{ key: 'vehicle', label: t('fuel.columns.vehicle'), value: (r: Refuel) => vehicleName(r.vehicle_id) }]
    : []),
  { key: 'odometer', label: t('fuel.columns.odometer'), num: true, value: (r) => km(r.odometer_km) },
  { key: 'litres', label: t('fuel.columns.litres'), num: true, value: (r) => num(r.litres, 2) },
  { key: 'price', label: t('fuel.columns.pricePerL'), num: true, value: (r) => money(r.price_per_l, 3) },
  { key: 'total', label: t('fuel.columns.total'), num: true, value: (r) => money(r.total) },
  {
    key: 'full',
    label: t('fuel.columns.tank'),
    value: (r) => (r.full_tank ? t('fuel.columns.full') : t('fuel.columns.partial')),
  },
  { key: 'cons', label: t('fuel.columns.consumption'), num: true, value: (r) => num(r.l_per_100km, 2) },
  { key: 'station', label: t('fuel.columns.station'), wrap: true, value: (r) => r.station ?? '' },
  { key: 'receipt', label: t('fuel.columns.receipt'), value: clip },
])

const readingColumns = computed<Column<OdometerReading>[]>(() => [
  { key: 'ts', label: t('fuel.columns.date'), value: (r) => fmtDateTime(r.ts) },
  ...(allVehicles.value
    ? [{ key: 'vehicle', label: t('fuel.columns.vehicle'), value: (r: OdometerReading) => vehicleName(r.vehicle_id) }]
    : []),
  { key: 'odometer', label: t('fuel.columns.odometer'), num: true, value: (r) => km(r.odometer_km) },
  { key: 'note', label: t('fuel.columns.note'), wrap: true, value: (r) => r.note ?? '' },
])

const refuelFields = computed<Field[]>(() => [
  vehicleField(),
  { key: 'ts', label: t('fuel.fields.ts'), type: 'datetime', required: true },
  {
    key: 'odometer_km', label: t('fuel.fields.odometer'), type: 'number', min: 0, half: true,
    hint: t('fuel.fields.odometerHint'),
  },
  { key: 'full_tank', label: t('fuel.fields.fullTank'), type: 'checkbox', half: true },
  { key: 'litres', label: t('fuel.fields.litres'), type: 'number', min: 0, half: true },
  { key: 'total', label: t('fuel.fields.total'), type: 'number', min: 0, half: true },
  {
    key: 'price_per_l',
    label: t('fuel.fields.pricePerL'),
    type: 'number',
    min: 0,
    hint: t('fuel.fields.pricePerLHint'),
  },
  { key: 'station', label: t('fuel.fields.station'), type: 'text' },
  { key: 'note', label: t('fuel.fields.note'), type: 'textarea' },
])

const readingFields = computed<Field[]>(() => [
  vehicleField(),
  { key: 'ts', label: t('fuel.fields.ts'), type: 'datetime', required: true },
  { key: 'odometer_km', label: t('fuel.fields.odometer'), type: 'number', min: 0, required: true },
  { key: 'note', label: t('fuel.fields.note'), type: 'textarea' },
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
      <div class="segmented" role="group" :aria-label="t('fuel.tabs.show')">
        <button :class="{ on: tab === 'refuels' }" :aria-pressed="tab === 'refuels'" @click="tab = 'refuels'">
          {{ t('fuel.tabs.refuels') }}
        </button>
        <button :class="{ on: tab === 'odometer' }" :aria-pressed="tab === 'odometer'" @click="tab = 'odometer'">
          {{ t('fuel.tabs.readings') }}
        </button>
      </div>
      <div class="actions">
        <a :href="exportUrl()" download><button>{{ t('fuel.actions.exportCsv') }}</button></a>
        <button class="primary" :disabled="!activeVehicles.length" @click="add">
          {{ tab === 'refuels' ? t('fuel.actions.addRefuel') : t('fuel.actions.addReading') }}
        </button>
      </div>
    </div>

    <template v-if="tab === 'refuels'">
      <p v-if="refuels.error.value" class="notice error">{{ refuels.error.value }}</p>
      <DataTable :columns="refuelColumns" :rows="refuels.items.value" :loading="refuels.loading.value"
        :empty="t('fuel.refuels.empty')" @edit="refuels.openEdit" @delete="refuels.remove">
        <template v-if="refuels.items.value.length" #foot>
          <tr>
            <td :colspan="allVehicles ? 3 : 2">
              {{ tn('fuel.refuels.count', refuels.items.value.length, { n: num(refuels.items.value.length) }) }}
            </td>
            <td class="num">{{ num(totals.litres, 1) }}</td>
            <td></td>
            <td class="num">{{ money(totals.cost) }}</td>
            <td colspan="4"></td>
          </tr>
        </template>
      </DataTable>
      <p class="small muted">{{ t('fuel.refuels.consumptionNote') }}</p>
    </template>

    <template v-else>
      <p v-if="readings.error.value" class="notice error">{{ readings.error.value }}</p>
      <DataTable :columns="readingColumns" :rows="readings.items.value" :loading="readings.loading.value"
        :empty="t('fuel.readings.empty')" @edit="readings.openEdit" @delete="readings.remove" />
    </template>

    <RecordDialog v-if="refuels.dialog.value"
      :title="refuels.dialog.value.mode === 'create' ? t('fuel.dialogs.addRefuel') : t('fuel.dialogs.editRefuel')"
      :fields="refuelFields" :initial="refuels.dialog.value.initial" :mode="refuels.dialog.value.mode"
      :save="refuels.save" attachments="refuels" @changed="refuels.load" @close="refuels.dialog.value = null" />
    <RecordDialog v-if="readings.dialog.value"
      :title="readings.dialog.value.mode === 'create' ? t('fuel.dialogs.addReading') : t('fuel.dialogs.editReading')"
      :fields="readingFields" :initial="readings.dialog.value.initial" :mode="readings.dialog.value.mode"
      :save="readings.save" @close="readings.dialog.value = null" />
  </div>
</template>
