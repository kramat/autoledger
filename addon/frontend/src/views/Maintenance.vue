<script setup lang="ts">
import { computed } from 'vue'
import { api, type MaintenanceRecord } from '../api'
import DataTable, { type Column } from '../components/DataTable.vue'
import RecordDialog from '../components/RecordDialog.vue'
import { defaultVehicleId, vehicleField, type Field } from '../components/fields'
import { fmtDate, isoDate, km, money } from '../format'
import { label, MAINTENANCE_CATEGORIES } from '../labels'
import { activeVehicles, state, vehicleName } from '../store'
import { useCrud } from '../useCrud'

const params = () => ({ vehicle_id: state.vehicleId || undefined })
const crud = useCrud<MaintenanceRecord>('maintenance', params, { noun: 'Maintenance entry' })

const columns = computed<Column<MaintenanceRecord>[]>(() => [
  { key: 'date', label: 'Date', value: (r) => fmtDate(r.date) },
  ...(!state.vehicleId
    ? [{ key: 'vehicle', label: 'Vehicle', value: (r: MaintenanceRecord) => vehicleName(r.vehicle_id) }]
    : []),
  { key: 'category', label: 'Category', value: (r) => label(MAINTENANCE_CATEGORIES, r.category) },
  { key: 'description', label: 'Description', wrap: true, value: (r) => r.description },
  { key: 'garage', label: 'Garage', wrap: true, value: (r) => r.garage ?? '' },
  { key: 'odometer', label: 'Odometer', num: true, value: (r) => km(r.odometer_km) },
  { key: 'cost', label: 'Cost', num: true, value: (r) => money(r.cost) },
])

const fields = computed<Field[]>(() => [
  vehicleField(),
  { key: 'date', label: 'Date', type: 'date', required: true, half: true },
  { key: 'category', label: 'Category', type: 'select', options: MAINTENANCE_CATEGORIES, required: true, half: true },
  { key: 'description', label: 'Description', type: 'text', required: true, placeholder: 'e.g. Yearly service + oil' },
  { key: 'odometer_km', label: 'Odometer (km)', type: 'number', min: 0, half: true },
  { key: 'cost', label: 'Cost', type: 'number', min: 0, half: true },
  { key: 'garage', label: 'Garage', type: 'text' },
  { key: 'note', label: 'Note', type: 'textarea' },
])

const total = computed(() => crud.items.value.reduce((sum, r) => sum + r.cost, 0))

function add(): void {
  crud.openCreate({ vehicle_id: defaultVehicleId(), date: isoDate(new Date()), category: 'service', cost: 0 })
}
</script>

<template>
  <div>
    <div class="page-head">
      <h2>Maintenance log</h2>
      <div class="actions">
        <a :href="api.exportUrl('maintenance', params())" download><button>Export CSV</button></a>
        <button class="primary" :disabled="!activeVehicles.length" @click="add">Add maintenance</button>
      </div>
    </div>
    <p v-if="crud.error.value" class="notice error">{{ crud.error.value }}</p>
    <DataTable :columns="columns" :rows="crud.items.value" :loading="crud.loading.value" empty="No maintenance logged yet."
      @edit="crud.openEdit" @delete="crud.remove">
      <template v-if="crud.items.value.length" #foot>
        <tr>
          <td :colspan="columns.length - 1">
            {{ crud.items.value.length }} {{ crud.items.value.length === 1 ? 'entry' : 'entries' }}
          </td>
          <td class="num">{{ money(total) }}</td>
          <td></td>
        </tr>
      </template>
    </DataTable>
    <RecordDialog v-if="crud.dialog.value"
      :title="crud.dialog.value.mode === 'create' ? 'Add maintenance' : 'Edit maintenance'" :fields="fields"
      :initial="crud.dialog.value.initial" :mode="crud.dialog.value.mode" :save="crud.save"
      @close="crud.dialog.value = null" />
  </div>
</template>
