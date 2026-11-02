<script setup lang="ts">
import { computed } from 'vue'
import { api, type Expense } from '../api'
import DataTable, { type Column } from '../components/DataTable.vue'
import RecordDialog from '../components/RecordDialog.vue'
import { defaultVehicleId, vehicleField, type Field } from '../components/fields'
import { fmtDate, isoDate, money } from '../format'
import { EXPENSE_CATEGORIES, label, RECURRENCES } from '../labels'
import { activeVehicles, state, vehicleName } from '../store'
import { useCrud } from '../useCrud'

const params = () => ({ vehicle_id: state.vehicleId || undefined })
const crud = useCrud<Expense>('expenses', params, { noun: 'Expense' })

function repeats(e: Expense): string {
  if (!e.recurrence) return 'One-off'
  const base = label(RECURRENCES, e.recurrence)
  return e.end_date ? `${base} until ${fmtDate(e.end_date)}` : base
}

const columns = computed<Column<Expense>[]>(() => [
  { key: 'date', label: 'Date', value: (e) => fmtDate(e.date) },
  ...(!state.vehicleId ? [{ key: 'vehicle', label: 'Vehicle', value: (e: Expense) => vehicleName(e.vehicle_id) }] : []),
  { key: 'category', label: 'Category', value: (e) => label(EXPENSE_CATEGORIES, e.category) },
  { key: 'amount', label: 'Amount', num: true, value: (e) => money(e.amount) },
  { key: 'repeats', label: 'Repeats', value: repeats },
  { key: 'note', label: 'Note', wrap: true, value: (e) => e.note ?? '' },
])

const recurring = (values: Record<string, unknown>) => values.recurrence != null

const fields = computed<Field[]>(() => [
  vehicleField(),
  { key: 'category', label: 'Category', type: 'select', options: EXPENSE_CATEGORIES, required: true, half: true },
  { key: 'amount', label: 'Amount', type: 'number', min: 0, required: true, half: true,
    hint: 'For a recurring cost: the amount per period, e.g. per year' },
  { key: 'recurrence', label: 'Repeats', type: 'select', options: RECURRENCES, half: true },
  { key: 'date', label: 'Date (start date when recurring)', type: 'date', required: true, half: true },
  { key: 'end_date', label: 'Ends on', type: 'date', show: recurring, hint: 'Leave empty if it is still running' },
  { key: 'note', label: 'Note', type: 'textarea' },
])

function add(): void {
  crud.openCreate({ vehicle_id: defaultVehicleId(), date: isoDate(new Date()), category: 'insurance', recurrence: null })
}
</script>

<template>
  <div>
    <div class="page-head">
      <h2>Other costs</h2>
      <div class="actions">
        <a :href="api.exportUrl('expenses', params())" download><button>Export CSV</button></a>
        <button class="primary" :disabled="!activeVehicles.length" @click="add">Add cost</button>
      </div>
    </div>
    <p v-if="crud.error.value" class="notice error">{{ crud.error.value }}</p>
    <DataTable :columns="columns" :rows="crud.items.value" :loading="crud.loading.value"
      empty="No costs yet. Add insurance, road tax, parking, tolls and other costs here." @edit="crud.openEdit"
      @delete="crud.remove" />
    <p class="small muted">
      Recurring costs are spread over the months they cover: a yearly insurance of 600 counts as 50 per month, up to
      the current month.
    </p>
    <RecordDialog v-if="crud.dialog.value" :title="crud.dialog.value.mode === 'create' ? 'Add cost' : 'Edit cost'"
      :fields="fields" :initial="crud.dialog.value.initial" :mode="crud.dialog.value.mode" :save="crud.save"
      @close="crud.dialog.value = null" />
  </div>
</template>
