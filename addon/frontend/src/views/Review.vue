<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, ApiError, type ReviewItem } from '../api'
import { fmtDateTime, money, num } from '../format'
import { REVIEW_REASONS } from '../labels'
import { activeVehicles, loadReviewCount, state, toast, vehicleName } from '../store'

type Action = 'update' | 'accept' | 'delete' | 'dismiss'

const items = ref<ReviewItem[]>([])
const loading = ref(true)
const error = ref('')
// Per-item form values for the quick actions.
// Number inputs hand back numbers, text inputs strings, so values are read loosely.
const forms = reactive<Record<string, Record<string, string | number>>>({})
const errors = reactive<Record<string, string>>({})

async function load(): Promise<void> {
  loading.value = true
  try {
    items.value = (await api.reviewItems()).items
    for (const item of items.value) {
      const r = item.record
      forms[item.id] ??= {
        litres: r?.litres != null ? String(r.litres) : '',
        total: '',
        energy_kwh: r?.energy_kwh != null ? String(r.energy_kwh) : '',
        price_per_kwh: r?.price_per_kwh != null ? String(r.price_per_kwh) : '',
        price_total: '',
        vehicle_id: activeVehicles.value.length === 1 ? activeVehicles.value[0].id : '',
      }
    }
    state.reviewCount = items.value.length
    error.value = ''
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    loading.value = false
  }
}

async function resolve(item: ReviewItem, action: Action, values: Record<string, unknown> = {}): Promise<void> {
  errors[item.id] = ''
  try {
    await api.resolve(item.id, action, values)
    toast(action === 'delete' ? 'Removed' : action === 'dismiss' ? 'Dismissed' : 'Saved')
    await load()
    await loadReviewCount()
  } catch (err) {
    errors[item.id] = err instanceof ApiError ? err.message : (err as Error).message
  }
}

function filled(value: string | number | undefined): boolean {
  return value !== undefined && String(value).trim() !== ''
}

function numberOrNull(value: string | number | undefined): number | null {
  return filled(value) ? Number(value) : null
}

function saveRefuel(item: ReviewItem): void {
  const f = forms[item.id]
  const values: Record<string, unknown> = { litres: numberOrNull(f.litres) }
  if (filled(f.total)) values.total = numberOrNull(f.total)
  resolve(item, 'update', values)
}

function saveCharge(item: ReviewItem): void {
  const f = forms[item.id]
  const values: Record<string, unknown> = { energy_kwh: numberOrNull(f.energy_kwh) }
  if (filled(f.price_total)) Object.assign(values, { price_mode: 'total', price_total: numberOrNull(f.price_total) })
  else Object.assign(values, { price_mode: 'per_kwh', price_per_kwh: numberOrNull(f.price_per_kwh) })
  resolve(item, 'update', values)
}

onMounted(load)
</script>

<template>
  <div class="stack">
    <div class="page-head" style="margin-bottom: 0">
      <h2>Review</h2>
    </div>
    <p v-if="error" class="notice error">{{ error }}</p>
    <div v-else-if="!loading && !items.length" class="card empty">Nothing to review. Everything is confirmed.</div>

    <section v-for="item in items" :key="item.id" class="card">
      <div class="vehicle-head">
        <h3>{{ REVIEW_REASONS[item.reason] ?? item.reason }}</h3>
        <span class="small muted">
          <template v-if="item.vehicle_id">{{ vehicleName(item.vehicle_id) }} · </template>{{ fmtDateTime(item.created_at) }}
        </span>
      </div>

      <!-- Refuel: confirm litres and enter the receipt total -->
      <template v-if="item.reason === 'refuel_price' && item.record">
        <p class="small muted">
          {{ fmtDateTime(item.record.ts) }}<template v-if="item.record.station"> at {{ item.record.station }}</template>.
          The fuel level rose by about {{ num(item.record.litres, 1) }} L. Suggested price
          {{ money(item.record.price_per_l, 3) }}/L ({{ money(item.record.total) }}).
        </p>
        <div class="form-grid" style="margin: 10px 0">
          <label class="field half"><span>Litres (from the receipt)</span>
            <input type="number" step="any" min="0" v-model="forms[item.id].litres" /></label>
          <label class="field half"><span>Total paid</span>
            <input type="number" step="any" min="0" v-model="forms[item.id].total" placeholder="From the receipt" /></label>
        </div>
        <div class="dialog-actions" style="justify-content: flex-start; flex-wrap: wrap">
          <button class="primary" @click="saveRefuel(item)">Save</button>
          <button @click="resolve(item, 'accept')">Keep suggestion</button>
          <button class="danger" @click="resolve(item, 'delete')">Not a refuel</button>
        </div>
      </template>

      <!-- Charge away from home -->
      <template v-else-if="(item.reason === 'public_charge_price' || item.reason === 'possible_engine_charge') && item.record">
        <p class="small muted">
          Between {{ fmtDateTime(item.record.start_ts) }} and {{ fmtDateTime(item.record.end_ts) }} the battery went from
          {{ num(item.record.soc_start) }} % to {{ num(item.record.soc_end) }} %, about
          {{ num(item.record.energy_kwh, 1) }} kWh<template v-if="item.record.address"> near {{ item.record.address }}</template>.
        </p>
        <div class="form-grid" style="margin: 10px 0">
          <label class="field half"><span>Energy (kWh)</span>
            <input type="number" step="any" min="0" v-model="forms[item.id].energy_kwh" /></label>
          <label class="field half"><span>Price per kWh</span>
            <input type="number" step="any" min="0" v-model="forms[item.id].price_per_kwh" /></label>
          <label class="field"><span>Or the total paid</span>
            <input type="number" step="any" min="0" v-model="forms[item.id].price_total" placeholder="Overrides the price per kWh" /></label>
        </div>
        <div class="dialog-actions" style="justify-content: flex-start; flex-wrap: wrap">
          <button class="primary" @click="saveCharge(item)">Save</button>
          <button @click="resolve(item, 'update', { price_mode: 'free' })">It was free</button>
          <button class="danger" @click="resolve(item, 'delete')">
            {{ item.reason === 'possible_engine_charge' ? 'Charged by the engine' : 'Not a charge' }}
          </button>
        </div>
      </template>

      <!-- Home charge without vehicle -->
      <template v-else-if="item.reason === 'charge_without_vehicle' && item.record">
        <p class="small muted">
          {{ fmtDateTime(item.record.start_ts) }}: {{ num(item.record.energy_kwh, 2) }} kWh for
          {{ money(item.record.cost) }} on {{ item.record.charger_name ?? 'the home charger' }}.
        </p>
        <div class="form-grid" style="margin: 10px 0">
          <label class="field half"><span>Vehicle</span>
            <select v-model="forms[item.id].vehicle_id">
              <option v-for="v in activeVehicles" :key="v.id" :value="v.id">{{ v.name }}</option>
            </select></label>
        </div>
        <div class="dialog-actions" style="justify-content: flex-start; flex-wrap: wrap">
          <button class="primary" :disabled="!forms[item.id].vehicle_id"
            @click="resolve(item, 'update', { vehicle_id: forms[item.id].vehicle_id })">Save</button>
          <button class="danger" @click="resolve(item, 'delete')">Remove session</button>
        </div>
      </template>

      <template v-else>
        <p class="small muted">{{ item.details?.error ?? 'No details' }} ({{ item.details?.type }})</p>
        <div class="dialog-actions" style="justify-content: flex-start">
          <button @click="resolve(item, 'dismiss')">Dismiss</button>
        </div>
      </template>

      <p v-if="errors[item.id]" class="notice error" style="margin-top: 10px">{{ errors[item.id] }}</p>
    </section>
  </div>
</template>
