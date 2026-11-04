<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { api, type Charge, type VehicleSummary } from '../api'
import DataTable, { type Column } from '../components/DataTable.vue'
import RecordDialog from '../components/RecordDialog.vue'
import { defaultVehicleId, vehicleField, type Field } from '../components/fields'
import { fmtDateTime, money, nowLocalInput, num } from '../format'
import { CHARGE_KINDS, FACTOR_MODES, label, PRICE_MODES } from '../labels'
import { t, tn } from '../i18n'
import { activeVehicles, loadReviewCount, loadVehicles, state, toast, vehicleName } from '../store'
import { useCrud } from '../useCrud'

const params = () => ({ vehicle_id: state.vehicleId || undefined })
const crud = useCrud<Charge>('charges', params, { noun: () => t('charging.nouns.charge'), afterChange: loadReviewCount })

function where(c: Charge): string {
  if (c.kind === 'home') return c.charger_name ?? t('common.labels.chargeKinds.home')
  return [c.provider, c.address].filter(Boolean).join(', ') || label(CHARGE_KINDS, c.kind)
}

function status(c: Charge): string {
  if (c.is_open) return t('charging.status.chargingNow')
  if (c.status === 'needs_review') return t('charging.status.needsPrice')
  if (c.energy_estimated) return t('charging.status.kwhEstimated')
  return ''
}

function battery(c: Charge): string {
  if (c.soc_start == null && c.soc_end == null) return '—'
  return `${num(c.soc_start)} → ${num(c.soc_end)} %`
}

const columns = computed<Column<Charge>[]>(() => [
  { key: 'start', label: t('charging.columns.start'), value: (c) => fmtDateTime(c.start_ts) },
  ...(!state.vehicleId
    ? [{ key: 'vehicle', label: t('common.app.filters.vehicle'), value: (c: Charge) => (c.vehicle_id ? vehicleName(c.vehicle_id) : '—') }]
    : []),
  { key: 'where', label: t('charging.columns.where'), wrap: true, value: where },
  { key: 'kwh', label: 'kWh', num: true, value: (c) => num(c.energy_kwh, 2) },
  { key: 'battery', label: t('charging.columns.battery'), value: battery },
  { key: 'price', label: t('charging.columns.perKwh'), num: true, value: (c) => money(c.avg_price, 3) },
  { key: 'cost', label: t('charging.columns.cost'), num: true, value: (c) => money(c.cost) },
  { key: 'status', label: t('charging.columns.status'), value: status },
])

const byMode = (mode: string) => (values: Record<string, unknown>) => values.price_mode === mode

const fields = computed<Field[]>(() => [
  vehicleField(),
  { key: 'kind', label: t('charging.fields.kind'), type: 'select', options: CHARGE_KINDS, half: true },
  { key: 'energy_kwh', label: t('charging.fields.energy'), type: 'number', min: 0, required: true, half: true },
  { key: 'start_ts', label: t('charging.fields.start'), type: 'datetime', required: true, half: true },
  { key: 'end_ts', label: t('charging.fields.end'), type: 'datetime', half: true },
  { key: 'price_mode', label: t('charging.fields.priceMode'), type: 'select', options: PRICE_MODES, required: true },
  { key: 'price_per_kwh', label: t('charging.fields.pricePerKwh'), type: 'number', min: 0, half: true, show: byMode('per_kwh') },
  { key: 'session_fee', label: t('charging.fields.sessionFee'), type: 'number', min: 0, half: true, show: byMode('per_kwh') },
  { key: 'price_total', label: t('charging.fields.priceTotal'), type: 'number', min: 0, show: byMode('total') },
  { key: 'soc_start', label: t('charging.fields.socStart'), type: 'number', min: 0, half: true },
  { key: 'soc_end', label: t('charging.fields.socEnd'), type: 'number', min: 0, half: true },
  { key: 'provider', label: t('charging.fields.provider'), type: 'text', half: true, placeholder: t('charging.fields.providerPlaceholder') },
  { key: 'address', label: t('charging.fields.address'), type: 'text', half: true },
  { key: 'note', label: t('charging.fields.note'), type: 'textarea' },
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
  toast(value == null ? t('charging.toast.usingLearned') : t('charging.toast.factorSaved'))
}

// The sentence about the factor, split around the part shown in bold.
function usesText(v: VehicleSummary): { before: string; factor: string; after: string } {
  const e = v.efficiency!
  const MARK = '\u0000'
  const sentence = t('charging.efficiency.uses', {
    factor: MARK,
    mode: label(FACTOR_MODES, e.mode),
    full: num(e.kwh_per_pct * 100, 1),
  })
  const [before, after = ''] = sentence.split(MARK)
  return { before, factor: t('charging.efficiency.factor', { value: num(e.kwh_per_pct, 3) }), after }
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
      <h2>{{ t('common.nav.charging') }}</h2>
      <div class="actions">
        <a :href="api.exportUrl('charges', params())" download><button>{{ t('charging.head.exportCsv') }}</button></a>
        <button class="primary" :disabled="!activeVehicles.length" @click="add">{{ t('charging.head.addPublic') }}</button>
      </div>
    </div>
    <p v-if="crud.error.value" class="notice error">{{ crud.error.value }}</p>
    <DataTable :columns="columns" :rows="crud.items.value" :loading="crud.loading.value"
      :empty="t('charging.empty')"
      @edit="crud.openEdit" @delete="crud.remove">
      <template v-if="crud.items.value.length" #foot>
        <tr>
          <td :colspan="state.vehicleId ? 2 : 3">
            {{ tn('charging.count', crud.items.value.length, { n: num(crud.items.value.length) }) }}
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
      {{ t('charging.footnote') }}
    </p>

    <section v-for="v in efficiency" :key="v.vehicle.id" class="card efficiency">
      <h2>{{ t('charging.efficiency.title', { name: v.vehicle.name }) }}</h2>
      <p>
        {{ usesText(v).before }}<b>{{ usesText(v).factor }}</b>{{ usesText(v).after }}
      </p>
      <p class="small muted">
        <template v-if="v.efficiency!.learned != null">
          {{ tn('charging.efficiency.learned', Math.min(v.efficiency!.learnable_sessions, 10), { value: num(v.efficiency!.learned, 3) }) }}
        </template>
        <template v-else>
          {{ t('charging.efficiency.learning', { n: num(v.efficiency!.learnable_sessions) }) }}
        </template>
        <template v-if="v.efficiency!.default != null"> {{ t('charging.efficiency.fromCapacity', { value: num(v.efficiency!.default, 3) }) }}</template>
      </p>
      <form class="factor-form" @submit.prevent="setFactor(v, Number(manualInput[v.vehicle.id]))">
        <label class="field">
          <span>{{ t('charging.efficiency.setYourself') }}</span>
          <input v-model="manualInput[v.vehicle.id]" type="number" step="0.001" min="0.01" max="2" required
            :placeholder="num(v.efficiency!.kwh_per_pct, 3)" />
        </label>
        <button type="submit">{{ t('common.actions.save') }}</button>
        <button v-if="v.efficiency!.mode === 'manual'" type="button" @click="setFactor(v, null)">
          {{ t('charging.efficiency.useLearned') }}
        </button>
      </form>
    </section>
    <RecordDialog v-if="crud.dialog.value" :title="crud.dialog.value.mode === 'create' ? t('charging.dialog.add') : t('charging.dialog.edit')"
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
