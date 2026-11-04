<script setup lang="ts">
import { computed } from 'vue'
import { api, type Expense } from '../api'
import DataTable, { type Column } from '../components/DataTable.vue'
import { clip } from '../attachments'
import RecordDialog from '../components/RecordDialog.vue'
import { defaultVehicleId, vehicleField, type Field } from '../components/fields'
import { fmtDate, isoDate, money } from '../format'
import { t } from '../i18n'
import { EXPENSE_CATEGORIES, label, RECURRENCES } from '../labels'
import { activeVehicles, state, vehicleName } from '../store'
import { useCrud } from '../useCrud'

const params = () => ({ vehicle_id: state.vehicleId || undefined })
const crud = useCrud<Expense>('expenses', params, { noun: () => t('costs.noun') })

function repeats(e: Expense): string {
  const base = label(RECURRENCES, e.recurrence)
  if (!e.recurrence || !e.end_date) return base
  return t('costs.repeatsUntil', { recurrence: base, date: fmtDate(e.end_date) })
}

const columns = computed<Column<Expense>[]>(() => [
  { key: 'date', label: t('costs.columns.date'), value: (e) => fmtDate(e.date) },
  ...(!state.vehicleId
    ? [{ key: 'vehicle', label: t('costs.columns.vehicle'), value: (e: Expense) => vehicleName(e.vehicle_id) }]
    : []),
  { key: 'category', label: t('costs.columns.category'), value: (e) => label(EXPENSE_CATEGORIES, e.category) },
  { key: 'amount', label: t('costs.columns.amount'), num: true, value: (e) => money(e.amount) },
  { key: 'repeats', label: t('costs.columns.repeats'), value: repeats },
  { key: 'note', label: t('costs.columns.note'), wrap: true, value: (e) => e.note ?? '' },
  { key: 'receipt', label: t('costs.columns.receipt'), value: clip },
])

const recurring = (values: Record<string, unknown>) => values.recurrence != null

const fields = computed<Field[]>(() => [
  vehicleField(),
  {
    key: 'category', label: t('costs.fields.category'), type: 'select', options: EXPENSE_CATEGORIES, required: true,
    half: true,
  },
  { key: 'amount', label: t('costs.fields.amount'), type: 'number', min: 0, required: true, half: true,
    hint: t('costs.fields.amountHint') },
  { key: 'recurrence', label: t('costs.fields.recurrence'), type: 'select', options: RECURRENCES, half: true },
  { key: 'date', label: t('costs.fields.date'), type: 'date', required: true, half: true },
  { key: 'end_date', label: t('costs.fields.endDate'), type: 'date', show: recurring, hint: t('costs.fields.endDateHint') },
  { key: 'note', label: t('costs.fields.note'), type: 'textarea' },
])

function add(): void {
  crud.openCreate({ vehicle_id: defaultVehicleId(), date: isoDate(new Date()), category: 'insurance', recurrence: null })
}
</script>

<template>
  <div>
    <div class="page-head">
      <h2>{{ t('costs.title') }}</h2>
      <div class="actions">
        <a :href="api.exportUrl('expenses', params())" download><button>{{ t('costs.actions.exportCsv') }}</button></a>
        <button class="primary" :disabled="!activeVehicles.length" @click="add">{{ t('costs.actions.add') }}</button>
      </div>
    </div>
    <p v-if="crud.error.value" class="notice error">{{ crud.error.value }}</p>
    <DataTable :columns="columns" :rows="crud.items.value" :loading="crud.loading.value"
      :empty="t('costs.empty')" @edit="crud.openEdit" @delete="crud.remove" />
    <p class="small muted">{{ t('costs.spreadNote') }}</p>
    <RecordDialog v-if="crud.dialog.value"
      :title="crud.dialog.value.mode === 'create' ? t('costs.dialogs.add') : t('costs.dialogs.edit')"
      :fields="fields" :initial="crud.dialog.value.initial" :mode="crud.dialog.value.mode" :save="crud.save"
      attachments="expenses" @changed="crud.load" @close="crud.dialog.value = null" />
  </div>
</template>
