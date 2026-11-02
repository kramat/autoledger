<script setup lang="ts">
import { computed } from 'vue'
import { api, type Charge } from '../api'
import DataTable, { type Column } from '../components/DataTable.vue'
import RecordDialog from '../components/RecordDialog.vue'
import { defaultVehicleId, vehicleField, type Field } from '../components/fields'
import { fmtDateTime, money, nowLocalInput, num } from '../format'
import { CHARGE_KINDS, label, PRICE_MODES } from '../labels'
import { activeVehicles, loadReviewCount, state, vehicleName } from '../store'
import { useCrud } from '../useCrud'

const params = () => ({ vehicle_id: state.vehicleId || undefined })
const crud = useCrud<Charge>('charges', params, { noun: 'Charge', afterChange: loadReviewCount })

function where(c: Charge): string {
  if (c.kind === 'home') return c.charger_name ?? 'Home'
  return [c.provider, c.address].filter(Boolean).join(', ') || label(CHARGE_KINDS, c.kind)
}

function status(c: Charge): string {
  if (c.is_open) return 'Charging now'
  if (c.status === 'needs_review') return 'Needs price'
  if (c.energy_estimated) return 'kWh estimated'
  return ''
}

function battery(c: Charge): string {
  if (c.soc_start == null && c.soc_end == null) return '—'
  return `${num(c.soc_start)} → ${num(c.soc_end)} %`
}

const columns = computed<Column<Charge>[]>(() => [
  { key: 'start', label: 'Start', value: (c) => fmtDateTime(c.start_ts) },
  ...(!state.vehicleId
    ? [{ key: 'vehicle', label: 'Vehicle', value: (c: Charge) => (c.vehicle_id ? vehicleName(c.vehicle_id) : '—') }]
    : []),
  { key: 'where', label: 'Where', wrap: true, value: where },
  { key: 'kwh', label: 'kWh', num: true, value: (c) => num(c.energy_kwh, 2) },
  { key: 'battery', label: 'Battery', value: battery },
  { key: 'price', label: 'Per kWh', num: true, value: (c) => money(c.avg_price, 3) },
  { key: 'cost', label: 'Cost', num: true, value: (c) => money(c.cost) },
  { key: 'status', label: 'Status', value: status },
])

const byMode = (mode: string) => (values: Record<string, unknown>) => values.price_mode === mode

const fields = computed<Field[]>(() => [
  vehicleField(),
  { key: 'kind', label: 'Type', type: 'select', options: CHARGE_KINDS, half: true },
  { key: 'energy_kwh', label: 'Energy (kWh)', type: 'number', min: 0, required: true, half: true },
  { key: 'start_ts', label: 'Start', type: 'datetime', required: true, half: true },
  { key: 'end_ts', label: 'End', type: 'datetime', half: true },
  { key: 'price_mode', label: 'Price', type: 'select', options: PRICE_MODES, required: true },
  { key: 'price_per_kwh', label: 'Price per kWh', type: 'number', min: 0, half: true, show: byMode('per_kwh') },
  { key: 'session_fee', label: 'Start fee', type: 'number', min: 0, half: true, show: byMode('per_kwh') },
  { key: 'price_total', label: 'Total paid', type: 'number', min: 0, show: byMode('total') },
  { key: 'soc_start', label: 'Battery at start (%)', type: 'number', min: 0, half: true },
  { key: 'soc_end', label: 'Battery at end (%)', type: 'number', min: 0, half: true },
  { key: 'provider', label: 'Provider', type: 'text', half: true, placeholder: 'e.g. Fastned' },
  { key: 'address', label: 'Location', type: 'text', half: true },
  { key: 'note', label: 'Note', type: 'textarea' },
])

const totals = computed(() => ({
  kwh: crud.items.value.reduce((sum, c) => sum + c.energy_kwh, 0),
  cost: crud.items.value.reduce((sum, c) => sum + c.cost, 0),
}))

function add(): void {
  crud.openCreate({
    vehicle_id: defaultVehicleId(),
    kind: 'public',
    start_ts: new Date(nowLocalInput()).toISOString(),
    price_mode: 'per_kwh',
    price_per_kwh: state.settings?.public_charge_price ?? null,
  })
}
</script>

<template>
  <div>
    <div class="page-head">
      <h2>Charging</h2>
      <div class="actions">
        <a :href="api.exportUrl('charges', params())" download><button>Export CSV</button></a>
        <button class="primary" :disabled="!activeVehicles.length" @click="add">Add public charge</button>
      </div>
    </div>
    <p v-if="crud.error.value" class="notice error">{{ crud.error.value }}</p>
    <DataTable :columns="columns" :rows="crud.items.value" :loading="crud.loading.value"
      empty="No charges yet. Home charging appears here automatically once the AutoLedger Collector is set up."
      @edit="crud.openEdit" @delete="crud.remove">
      <template v-if="crud.items.value.length" #foot>
        <tr>
          <td :colspan="state.vehicleId ? 2 : 3">
            {{ crud.items.value.length }} {{ crud.items.value.length === 1 ? 'charge' : 'charges' }}
          </td>
          <td class="num">{{ num(totals.kwh, 1) }}</td>
          <td></td>
          <td class="num">{{ totals.kwh ? money(totals.cost / totals.kwh, 3) : '—' }}</td>
          <td class="num">{{ money(totals.cost) }}</td>
          <td colspan="2"></td>
        </tr>
      </template>
    </DataTable>
    <p class="small muted">
      Home sessions are priced per kWh at the moment it was delivered, using your electricity price sensor. Edit a
      session to set your own price, a total, or mark it free.
    </p>
    <RecordDialog v-if="crud.dialog.value" :title="crud.dialog.value.mode === 'create' ? 'Add charge' : 'Edit charge'"
      :fields="fields" :initial="crud.dialog.value.initial" :mode="crud.dialog.value.mode" :save="crud.save"
      @close="crud.dialog.value = null" />
  </div>
</template>
