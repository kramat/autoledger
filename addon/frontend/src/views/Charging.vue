<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { api, type Charge, type VehicleSummary } from '../api'
import DataTable, { type Column } from '../components/DataTable.vue'
import RecordDialog from '../components/RecordDialog.vue'
import { defaultVehicleId, vehicleField, type Field } from '../components/fields'
import { fmtDateTime, money, nowLocalInput, num } from '../format'
import { CHARGE_KINDS, FACTOR_MODES, label, PRICE_MODES } from '../labels'
import { activeVehicles, loadReviewCount, loadVehicles, state, toast, vehicleName } from '../store'
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

// --- Efficiency: wall kWh per battery % (docs/costs.md#kwh-per-percent) --------

const efficiency = ref<VehicleSummary[]>([])
const manualInput = reactive<Record<string, string>>({})

async function loadEfficiency(): Promise<void> {
  const summary = await api.summary({ vehicle_id: state.vehicleId || undefined, months: 1 })
  efficiency.value = summary.vehicles.filter((v) => v.vehicle.type !== 'ICE' && v.efficiency)
}
watch(() => [state.vehicleId, crud.items.value], () => loadEfficiency().catch(() => undefined), { immediate: true })

async function setFactor(v: VehicleSummary, value: number | null): Promise<void> {
  await api.update('vehicles', v.vehicle.id, { kwh_per_pct: value })
  await loadVehicles()
  await loadEfficiency()
  manualInput[v.vehicle.id] = ''
  toast(value == null ? 'Using the learned value' : 'kWh per % saved')
}

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

    <section v-for="v in efficiency" :key="v.vehicle.id" class="card efficiency">
      <h2>Efficiency · {{ v.vehicle.name }}</h2>
      <p>
        Trips use <b>{{ num(v.efficiency!.kwh_per_pct, 3) }} kWh from the wall per battery %</b>
        ({{ label(FACTOR_MODES, v.efficiency!.mode) }}), so a full battery costs
        {{ num(v.efficiency!.kwh_per_pct * 100, 1) }} kWh of charging, losses included.
      </p>
      <p class="small muted">
        <template v-if="v.efficiency!.learned != null">
          Learned: {{ num(v.efficiency!.learned, 3) }}, the median of the last {{ Math.min(v.efficiency!.learnable_sessions, 10) }}
          home charges that added at least 20 %.
        </template>
        <template v-else>
          Learning needs 3 home charges that add at least 20 % with the battery % known; {{ v.efficiency!.learnable_sessions }} so far.
        </template>
        <template v-if="v.efficiency!.default != null"> From the battery capacity: {{ num(v.efficiency!.default, 3) }}.</template>
      </p>
      <form class="factor-form" @submit.prevent="setFactor(v, Number(manualInput[v.vehicle.id]))">
        <label class="field">
          <span>Set it yourself (kWh per %)</span>
          <input v-model="manualInput[v.vehicle.id]" type="number" step="0.001" min="0.01" max="2" required
            :placeholder="num(v.efficiency!.kwh_per_pct, 3)" />
        </label>
        <button type="submit">Save</button>
        <button v-if="v.efficiency!.mode === 'manual'" type="button" @click="setFactor(v, null)">
          Use the learned value
        </button>
      </form>
    </section>
    <RecordDialog v-if="crud.dialog.value" :title="crud.dialog.value.mode === 'create' ? 'Add charge' : 'Edit charge'"
      :fields="fields" :initial="crud.dialog.value.initial" :mode="crud.dialog.value.mode" :save="crud.save"
      @close="crud.dialog.value = null" />
  </div>
</template>

<style scoped>
.efficiency {
  margin-top: 16px;
}
.factor-form {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  flex-wrap: wrap;
}
.factor-form .field {
  max-width: 220px;
}
</style>
