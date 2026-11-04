<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type Vehicle } from '../api'
import DataTable, { type Column } from '../components/DataTable.vue'
import RecordDialog from '../components/RecordDialog.vue'
import type { Field } from '../components/fields'
import { fmtDate, isoDate, km, num } from '../format'
import { t } from '../i18n'
import { FUEL_TYPES, label, VEHICLE_TYPES } from '../labels'
import { loadVehicles, toast } from '../store'
import { useTheme } from '../theme'
import { useCrud } from '../useCrud'

const route = useRoute()
const router = useRouter()
const theme = useTheme()
const crud = useCrud<Vehicle>('vehicles', () => ({}), { noun: () => t('vehicles.noun'), afterChange: loadVehicles })

function capacity(v: Vehicle): string {
  const parts = []
  if (v.tank_l) parts.push(`${num(v.tank_l)} L`)
  if (v.battery_usable_kwh) parts.push(`${num(v.battery_usable_kwh, 1)} kWh`)
  return parts.join(' · ') || '—'
}

const columns = computed<Column<Vehicle>[]>(() => [
  {
    key: 'name',
    label: t('vehicles.columns.name'),
    value: (v) => (v.archived_at ? t('vehicles.columns.archivedName', { name: v.name }) : v.name),
  },
  { key: 'type', label: t('vehicles.columns.type'), value: (v) => label(VEHICLE_TYPES, v.type) },
  { key: 'fuel', label: t('vehicles.columns.fuel'), value: (v) => label(FUEL_TYPES, v.fuel_type) },
  { key: 'plate', label: t('vehicles.columns.plate'), value: (v) => v.plate ?? '' },
  { key: 'capacity', label: t('vehicles.columns.capacity'), value: capacity },
  {
    key: 'start',
    label: t('vehicles.columns.start'),
    value: (v) => t('vehicles.columns.startValue', { odometer: km(v.start_odometer_km), date: fmtDate(v.start_date) }),
  },
])

const hasEngine = (values: Record<string, unknown>) => values.type !== 'BEV'
const hasBattery = (values: Record<string, unknown>) => values.type !== 'ICE'

const fields = computed<Field[]>(() => [
  {
    key: 'name', label: t('vehicles.fields.name'), type: 'text', required: true,
    placeholder: t('vehicles.fields.namePlaceholder'),
  },
  { key: 'make', label: t('vehicles.fields.make'), type: 'text', half: true },
  { key: 'model', label: t('vehicles.fields.model'), type: 'text', half: true },
  { key: 'year', label: t('vehicles.fields.year'), type: 'number', step: '1', half: true },
  { key: 'plate', label: t('vehicles.fields.plate'), type: 'text', half: true },
  { key: 'type', label: t('vehicles.fields.type'), type: 'select', options: VEHICLE_TYPES, required: true, half: true },
  { key: 'fuel_type', label: t('vehicles.fields.fuel'), type: 'select', options: FUEL_TYPES.filter((f) => f.value !== 'none'),
    half: true, show: hasEngine },
  { key: 'tank_l', label: t('vehicles.fields.tank'), type: 'number', min: 0, half: true, show: hasEngine },
  {
    key: 'battery_usable_kwh', label: t('vehicles.fields.battery'), type: 'number', min: 0, half: true,
    show: hasBattery,
  },
  { key: 'kwh_per_pct', label: t('vehicles.fields.kwhPerPct'), type: 'number', min: 0, step: 'any', show: hasBattery,
    hint: t('vehicles.fields.kwhPerPctHint') },
  { key: 'start_date', label: t('vehicles.fields.startDate'), type: 'date', required: true, half: true,
    hint: t('vehicles.fields.startDateHint') },
  {
    key: 'start_odometer_km', label: t('vehicles.fields.startOdometer'), type: 'number', min: 0, required: true,
    half: true,
  },
  { key: 'purchase_date', label: t('vehicles.fields.purchaseDate'), type: 'date', half: true },
  { key: 'purchase_price', label: t('vehicles.fields.purchasePrice'), type: 'number', min: 0, half: true },
  { key: 'resale_date', label: t('vehicles.fields.resaleDate'), type: 'date', half: true },
  { key: 'resale_estimate', label: t('vehicles.fields.resaleEstimate'), type: 'number', min: 0, half: true },
  { key: 'depreciation_enabled', label: t('vehicles.fields.depreciation'), type: 'checkbox',
    hint: t('vehicles.fields.depreciationHint') },
  { key: 'color', label: t('vehicles.fields.color'), type: 'color', half: true },
  { key: 'note', label: t('vehicles.fields.note'), type: 'textarea' },
])

function add(): void {
  crud.openCreate({
    type: 'ICE',
    fuel_type: 'petrol',
    start_date: isoDate(new Date()),
    color: theme.value.series[crud.items.value.length % 4],
  })
}

async function saveVehicle(data: Record<string, unknown>): Promise<Vehicle | undefined> {
  // An electric car has no fuel; the field is hidden, so send it explicitly.
  if (data.type === 'BEV') data.fuel_type = 'none'
  else if (data.type && crud.dialog.value?.initial.fuel_type === 'none' && !data.fuel_type) data.fuel_type = 'petrol'
  return crud.save(data)
}

async function toggleArchive(v: Vehicle): Promise<void> {
  await api.update('vehicles', v.id, { archived: !v.archived_at })
  await loadVehicles()
  await crud.load()
  toast(t(v.archived_at ? 'vehicles.toast.restored' : 'vehicles.toast.archived', { name: v.name }))
}

onMounted(() => {
  if (route.query.new === '1') {
    add()
    const { new: _ignored, ...rest } = route.query
    router.replace({ query: rest })
  }
})

const archiveAction = {
  label: (v: Vehicle) => (v.archived_at ? t('vehicles.unarchive') : t('vehicles.archive')),
  run: toggleArchive,
}

const archivedCount = computed(() => crud.items.value.filter((v) => v.archived_at).length)
</script>

<template>
  <div>
    <div class="page-head">
      <h2>{{ t('vehicles.title') }}</h2>
      <div class="actions">
        <button class="primary" @click="add">{{ t('vehicles.add') }}</button>
      </div>
    </div>
    <p v-if="crud.error.value" class="notice error">{{ crud.error.value }}</p>
    <DataTable :columns="columns" :rows="crud.items.value" :loading="crud.loading.value" :empty="t('vehicles.empty')"
      :extra="archiveAction" @edit="crud.openEdit" @delete="crud.remove" />
    <p class="small muted">
      {{ t('vehicles.archivedNote') }}
      <template v-if="archivedCount"> {{ t('vehicles.archivedCount', { n: num(archivedCount) }) }}</template>
    </p>
    <RecordDialog v-if="crud.dialog.value"
      :title="crud.dialog.value.mode === 'create' ? t('vehicles.dialogs.add') : t('vehicles.dialogs.edit')"
      :fields="fields" :initial="crud.dialog.value.initial" :mode="crud.dialog.value.mode" :save="saveVehicle"
      @close="crud.dialog.value = null" />
  </div>
</template>
