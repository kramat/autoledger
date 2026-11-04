<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, ApiError, type IdleRecord, type Trip } from '../api'
import DataTable, { type Column } from '../components/DataTable.vue'
import RecordDialog from '../components/RecordDialog.vue'
import TripMap from '../components/TripMap.vue'
import { defaultVehicleId, vehicleField, type Field } from '../components/fields'
import { fmtDate, fmtDateTime, fromLocalInput, money, nowLocalInput, num, toLocalInput } from '../format'
import { locale, t, tn } from '../i18n'
import { FACTOR_MODES, label, TRIP_KINDS } from '../labels'
import { activeVehicles, periodRange, state, toast, vehicleName } from '../store'
import { useCrud } from '../useCrud'

const params = () => ({ vehicle_id: state.vehicleId || undefined, ...periodRange() })
const trips = useCrud<Trip>('trips', params, { noun: () => t('trips.nouns.trip') })
const idle = useCrud<IdleRecord>('idle-records', params, { noun: () => t('trips.nouns.record') })
const view = ref<'list' | 'map'>('list')
const detailId = ref<string | null>(null)
const detail = computed(() => trips.items.value.find((trip) => trip.id === detailId.value) ?? null)

function time(value: string): string {
  return new Date(value).toLocaleTimeString(locale(), { hour: '2-digit', minute: '2-digit' })
}

function place(address: string | null, zone: string | null): string {
  return address ?? zone ?? '—'
}

function route(trip: Trip): string {
  const from = place(trip.start_address, trip.start_zone)
  if (trip.kind === 'round_trip') return `⟲ ${trip.start_zone ?? from}`
  return `${from} → ${place(trip.end_address, trip.end_zone)}`
}

function fuel(trip: Trip): string {
  const litres = trip.costing?.fuel_l ?? trip.fuel_l
  if (!litres) return '—'
  return `${num(litres, 1)}${trip.costing?.fuel_reconciled ? ' ✓' : ''}`
}

function perKm(trip: Trip): string {
  return trip.costing && trip.distance_km >= 1 ? money(trip.costing.cost / trip.distance_km, 3) : '—'
}

const DISTANCE_SOURCE_KEYS = {
  trip_meter: 'trips.detail.distanceSources.trip_meter',
  odometer: 'trips.detail.distanceSources.odometer',
  manual: 'trips.detail.distanceSources.manual',
} as const

function distanceSource(trip: Trip): string {
  const key = DISTANCE_SOURCE_KEYS[trip.distance_source] as (typeof DISTANCE_SOURCE_KEYS)[keyof typeof DISTANCE_SOURCE_KEYS] | undefined
  return key ? t(key) : trip.distance_source
}

const columns = computed<Column<Trip>[]>(() => [
  { key: 'date', label: t('trips.columns.date'), value: (trip) => `${fmtDate(trip.start_ts)} ${trip.start_ts_estimated ? '~' : ''}${time(trip.start_ts)}–${time(trip.end_ts)}` },
  ...(!state.vehicleId ? [{ key: 'vehicle', label: t('common.app.filters.vehicle'), value: (trip: Trip) => vehicleName(trip.vehicle_id) }] : []),
  { key: 'route', label: t('trips.columns.route'), wrap: true, value: route },
  { key: 'km', label: 'km', num: true, value: (trip) => num(trip.distance_km, 1) },
  { key: 'kwh', label: 'kWh', num: true, value: (trip) => (trip.costing?.energy_kwh ? num(trip.costing.energy_kwh, 2) : '—') },
  { key: 'fuel', label: 'L', num: true, value: fuel },
  { key: 'cost', label: t('trips.columns.cost'), num: true, value: (trip) => money(trip.costing?.cost) },
  { key: 'per_km', label: t('trips.columns.perKm'), num: true, value: perKm },
])

const totals = computed(() => {
  const list = trips.items.value
  const km = list.reduce((s, trip) => s + trip.distance_km, 0)
  const kwh = list.reduce((s, trip) => s + Math.max(trip.costing?.energy_kwh ?? 0, 0), 0)
  const litres = list.reduce((s, trip) => s + (trip.costing?.fuel_l ?? 0), 0)
  const cost = list.reduce((s, trip) => s + (trip.costing?.cost ?? 0), 0)
  return { km, kwh, litres, cost }
})

const idleTotals = computed(() => ({
  kwh: idle.items.value.reduce((s, r) => s + (r.costing?.energy_kwh ?? 0), 0),
  cost: idle.items.value.reduce((s, r) => s + (r.costing?.cost ?? 0), 0),
}))

const idleColumns = computed<Column<IdleRecord>[]>(() => [
  { key: 'when', label: t('trips.idle.columns.parked'), value: (r) => `${fmtDateTime(r.start_ts)} – ${time(r.end_ts)}` },
  ...(!state.vehicleId ? [{ key: 'vehicle', label: t('common.app.filters.vehicle'), value: (r: IdleRecord) => vehicleName(r.vehicle_id) }] : []),
  { key: 'zone', label: t('trips.idle.columns.where'), value: (r) => r.zone ?? '—' },
  { key: 'battery', label: t('trips.idle.columns.battery'), num: true, value: (r) => (r.battery_used_pct ? `−${num(r.battery_used_pct, 1)} %` : '—') },
  { key: 'kwh', label: 'kWh', num: true, value: (r) => (r.costing?.energy_kwh ? num(r.costing.energy_kwh, 2) : '—') },
  { key: 'fuel', label: 'L', num: true, value: (r) => (r.fuel_l ? num(r.fuel_l, 1) : '—') },
  { key: 'cost', label: t('trips.idle.columns.cost'), num: true, value: (r) => money(r.costing?.cost) },
])

const tripFields = computed<Field[]>(() => [
  vehicleField(),
  { key: 'start_ts', label: t('trips.fields.start'), type: 'datetime', required: true, half: true },
  { key: 'end_ts', label: t('trips.fields.end'), type: 'datetime', required: true, half: true },
  { key: 'start_address', label: t('trips.fields.from'), type: 'text', half: true },
  { key: 'end_address', label: t('trips.fields.to'), type: 'text', half: true },
  { key: 'kind', label: t('trips.fields.kind'), type: 'select', options: TRIP_KINDS, half: true },
  { key: 'distance_km', label: t('trips.fields.distance'), type: 'number', min: 0, required: true, half: true },
  { key: 'battery_start_pct', label: t('trips.fields.batteryStart'), type: 'number', min: 0, half: true },
  { key: 'battery_end_pct', label: t('trips.fields.batteryEnd'), type: 'number', min: 0, half: true },
  { key: 'energy_kwh', label: t('trips.fields.energy'), type: 'number', half: true,
    hint: t('trips.fields.energyHint') },
  { key: 'fuel_l', label: t('trips.fields.fuel'), type: 'number', min: 0, half: true },
  { key: 'note', label: t('trips.fields.note'), type: 'textarea' },
])

const idleFields = computed<Field[]>(() => [
  { key: 'zone', label: t('trips.idle.fields.where'), type: 'text' },
  { key: 'battery_used_pct', label: t('trips.idle.fields.batteryUsed'), type: 'number', half: true },
  { key: 'energy_kwh', label: t('trips.fields.energy'), type: 'number', half: true,
    hint: t('trips.fields.energyHint') },
  { key: 'fuel_l', label: t('trips.fields.fuel'), type: 'number', min: 0, half: true },
  { key: 'note', label: t('trips.fields.note'), type: 'textarea' },
])

function add(): void {
  const now = nowLocalInput()
  trips.openCreate({
    vehicle_id: defaultVehicleId(),
    start_ts: new Date(now).toISOString(),
    end_ts: new Date(now).toISOString(),
    kind: 'one_way',
    fuel_l: 0,
  })
}

// --- Detail panel: explanation, split and merge -------------------------------

const split = ref<{ km: string; at: string; address: string } | null>(null)
const busy = ref(false)
const actionError = ref('')

function openDetail(trip: Trip): void {
  detailId.value = trip.id
  split.value = null
  actionError.value = ''
}

/** Trips of the same vehicle directly before and after, in time order. */
const neighbours = computed(() => {
  const current = detail.value
  if (!current) return { prev: null, next: null }
  const same = trips.items.value.filter((x) => x.vehicle_id === current.vehicle_id).sort((a, b) => a.start_ts.localeCompare(b.start_ts))
  const i = same.findIndex((x) => x.id === current.id)
  return { prev: same[i - 1] ?? null, next: same[i + 1] ?? null }
})

async function restoreAll(created: string[], originals: string[]): Promise<void> {
  for (const id of created) await api.remove('trips', id)
  for (const id of originals) await api.restore('trips', id)
  await trips.load()
}

async function merge(other: Trip): Promise<void> {
  const current = detail.value
  if (!current) return
  busy.value = true
  actionError.value = ''
  try {
    const merged = await api.mergeTrips([current.id, other.id])
    await trips.load()
    detailId.value = merged.id
    toast(t('trips.detail.toast.merged'), t('common.actions.undo'), () => restoreAll([merged.id], [current.id, other.id]))
  } catch (err) {
    actionError.value = (err as Error).message
  } finally {
    busy.value = false
  }
}

function startSplit(): void {
  const current = detail.value
  if (!current) return
  const middle = new Date((new Date(current.start_ts).getTime() + new Date(current.end_ts).getTime()) / 2).toISOString()
  split.value = { km: String(Math.round((current.distance_km / 2) * 10) / 10), at: toLocalInput(middle), address: '' }
}

async function doSplit(): Promise<void> {
  const current = detail.value
  if (!current || !split.value) return
  busy.value = true
  actionError.value = ''
  try {
    const parts = await api.splitTrip(current.id, {
      at_km: Number(split.value.km),
      at_ts: fromLocalInput(split.value.at),
      address: split.value.address.trim() || null,
    })
    await trips.load()
    detailId.value = parts[0].id
    split.value = null
    toast(t('trips.detail.toast.split'), t('common.actions.undo'), () => restoreAll(parts.map((p) => p.id), [current.id]))
  } catch (err) {
    actionError.value = err instanceof ApiError ? Object.values(err.fields)[0] ?? err.message : (err as Error).message
  } finally {
    busy.value = false
  }
}

function editDetail(): void {
  if (!detail.value) return
  trips.openEdit(detail.value)
  detailId.value = null
}

async function deleteDetail(): Promise<void> {
  if (!detail.value) return
  const current = detail.value
  detailId.value = null
  await trips.remove(current)
}

const showIdle = computed(() => idle.items.value.length > 0)
const noCollector = computed(() =>
  activeVehicles.value.filter((v) => !state.vehicleId || v.id === state.vehicleId).every((v) => v.tracking !== 'collector'),
)
</script>

<template>
  <div class="stack">
    <div class="page-head">
      <h2>{{ t('common.nav.trips') }}</h2>
      <div class="actions">
        <div class="segmented" role="group" :aria-label="t('trips.head.display')">
          <button :class="{ on: view === 'list' }" :aria-pressed="view === 'list'" @click="view = 'list'">{{ t('trips.head.list') }}</button>
          <button :class="{ on: view === 'map' }" :aria-pressed="view === 'map'" @click="view = 'map'">{{ t('trips.head.map') }}</button>
        </div>
        <a :href="api.exportUrl('trips', params())" download><button>{{ t('trips.head.exportCsv') }}</button></a>
        <button class="primary" :disabled="!activeVehicles.length" @click="add">{{ t('trips.head.add') }}</button>
      </div>
    </div>
    <p v-if="trips.error.value" class="notice error">{{ trips.error.value }}</p>

    <div v-if="trips.items.value.length" class="stats card">
      <div class="stat"><div class="label">{{ t('common.nav.trips') }}</div><div class="value">{{ num(trips.items.value.length) }}</div>
        <div class="sub">{{ num(totals.km, 1) }} km</div></div>
      <div class="stat"><div class="label">{{ t('trips.stats.electricity') }}</div><div class="value">{{ num(totals.kwh, 1) }} kWh</div>
        <div class="sub">{{ totals.km >= 1 ? `${num((totals.kwh / totals.km) * 100, 1)} kWh/100 km` : '—' }}</div></div>
      <div class="stat"><div class="label">{{ t('trips.stats.fuel') }}</div><div class="value">{{ num(totals.litres, 1) }} L</div>
        <div class="sub">{{ totals.km >= 1 ? `${num((totals.litres / totals.km) * 100, 1)} L/100 km` : '—' }}</div></div>
      <div class="stat"><div class="label">{{ t('trips.stats.cost') }}</div><div class="value">{{ money(totals.cost) }}</div>
        <div class="sub">{{ totals.km >= 1 ? t('trips.stats.perKm', { amount: money(totals.cost / totals.km, 3) }) : '—' }}</div></div>
    </div>

    <TripMap v-if="view === 'map'" :trips="trips.items.value" :selected="detailId" @select="openDetail" />
    <DataTable v-else :columns="columns" :rows="trips.items.value" :loading="trips.loading.value"
      :empty="noCollector ? t('trips.empty.noCollector') : t('trips.empty.none')"
      :extra="{ label: () => t('trips.details'), run: openDetail }" @edit="trips.openEdit" @delete="trips.remove" />
    <p class="small muted">{{ t('trips.footnote') }}</p>

    <section v-if="showIdle" class="card">
      <h2>{{ t('trips.idle.title') }}</h2>
      <p class="small muted">{{ t('trips.idle.intro') }}</p>
      <DataTable :columns="idleColumns" :rows="idle.items.value" empty="" @edit="idle.openEdit" @delete="idle.remove">
        <template #foot>
          <tr>
            <td :colspan="state.vehicleId ? 3 : 4">{{ tn('trips.idle.records', idle.items.value.length, { n: num(idle.items.value.length) }) }}</td>
            <td class="num">{{ num(idleTotals.kwh, 2) }}</td>
            <td></td>
            <td class="num">{{ money(idleTotals.cost) }}</td>
            <td></td>
          </tr>
        </template>
      </DataTable>
    </section>

    <div v-if="detail" class="overlay" @click.self="detailId = null">
      <div class="dialog" role="dialog" aria-modal="true" :aria-label="t('trips.detail.ariaLabel')">
        <h2>{{ route(detail) }}</h2>
        <p class="small muted" style="margin-top: -6px">
          {{ fmtDateTime(detail.start_ts) }} – {{ time(detail.end_ts) }}
          <template v-if="detail.start_ts_estimated"> · {{ t('trips.detail.startEstimated') }}</template>
          · {{ num(detail.distance_km, 1) }} km
          ({{ distanceSource(detail) }})
        </p>

        <dl class="facts">
          <template v-if="detail.odometer_start != null">
            <dt>{{ t('trips.detail.facts.odometer') }}</dt><dd>{{ num(detail.odometer_start) }} → {{ num(detail.odometer_end) }} km</dd>
          </template>
          <template v-if="detail.battery_used_pct != null">
            <dt>{{ t('trips.detail.facts.battery') }}</dt>
            <dd>{{ t('trips.detail.facts.batteryValue', {
              start: num(detail.battery_start_pct, 1),
              end: num(detail.battery_end_pct, 1),
              used: num(detail.battery_used_pct, 1),
            }) }}</dd>
          </template>
          <template v-if="detail.charged_kwh">
            <dt>{{ t('trips.detail.facts.chargedBetween') }}</dt><dd>{{ num(detail.charged_kwh, 2) }} kWh</dd>
          </template>
          <template v-if="detail.fuel_start_l != null">
            <dt>{{ t('trips.detail.facts.tank') }}</dt><dd>{{ num(detail.fuel_start_l, 1) }} → {{ num(detail.fuel_end_l, 1) }} L</dd>
          </template>
        </dl>

        <template v-if="detail.costing">
          <h3 class="small">{{ t('trips.detail.explain.title') }}</h3>
          <table class="explain">
            <tbody>
              <tr>
                <td>{{ t('trips.detail.explain.electricity') }}</td>
                <td>
                  <template v-if="detail.costing.kwh_per_pct != null && detail.battery_used_pct != null">
                    {{ num(detail.battery_used_pct, 1) }} % × {{ num(detail.costing.kwh_per_pct, 3) }} kWh/%
                    ({{ label(FACTOR_MODES, detail.costing.factor_mode) }})<template v-if="detail.charged_kwh"> + {{ num(detail.charged_kwh, 2) }} kWh</template>
                    =
                  </template>
                  {{ num(detail.costing.energy_kwh, 2) }} kWh × {{ money(detail.costing.kwh_price, 3) }}
                </td>
                <td class="num">{{ money(detail.costing.electricity_cost) }}</td>
              </tr>
              <tr>
                <td>{{ t('trips.detail.explain.fuel') }}</td>
                <td>
                  {{ num(detail.costing.fuel_l, 2) }} L
                  <template v-if="detail.costing.fuel_reconciled">{{ t('trips.detail.explain.fuelReconciled', { measured: num(detail.costing.fuel_l_measured, 2) }) }}</template>
                  <template v-else-if="Math.abs(detail.costing.fuel_l_measured - detail.costing.fuel_l) >= 0.005">{{
                    t('trips.detail.explain.fuelSmoothed', { measured: num(detail.costing.fuel_l_measured, 2) }) }}</template>
                  <template v-else-if="detail.costing.fuel_l">{{ t('trips.detail.explain.fuelProvisional') }}</template>
                  × {{ money(detail.costing.l_price, 3) }}
                </td>
                <td class="num">{{ money(detail.costing.fuel_cost) }}</td>
              </tr>
              <tr class="total">
                <td>{{ t('trips.detail.explain.trip') }}</td>
                <td>{{ t('trips.detail.explain.perKm', { amount: perKm(detail) }) }}</td>
                <td class="num">{{ money(detail.costing.cost) }}</td>
              </tr>
            </tbody>
          </table>
          <p class="small muted">{{ t('trips.detail.explain.pricesNote') }}</p>
          <ul v-if="detail.costing.notes.length" class="small">
            <li v-for="n in detail.costing.notes" :key="n">{{ n }}</li>
          </ul>
        </template>
        <p v-if="detail.note" class="small">{{ detail.note }}</p>

        <form v-if="split" class="form-grid split" @submit.prevent="doSplit">
          <label class="field half"><span>{{ t('trips.detail.split.stopAfter') }}</span>
            <input v-model="split.km" type="number" step="0.1" min="0.1" required /></label>
          <label class="field half"><span>{{ t('trips.detail.split.stopTime') }}</span>
            <input v-model="split.at" type="datetime-local" required /></label>
          <label class="field"><span>{{ t('trips.detail.split.stopPlace') }}</span>
            <input v-model="split.address" type="text" :placeholder="t('trips.detail.split.stopPlacePlaceholder')" /></label>
          <div class="dialog-actions" style="grid-column: 1 / -1">
            <button type="button" @click="split = null">{{ t('common.actions.cancel') }}</button>
            <button type="submit" class="primary" :disabled="busy">{{ t('trips.detail.split.submit') }}</button>
          </div>
        </form>
        <p v-if="actionError" class="notice error">{{ actionError }}</p>

        <div v-if="!split" class="dialog-actions wrap">
          <button v-if="neighbours.prev" :disabled="busy" @click="merge(neighbours.prev)">{{ t('trips.detail.actions.mergePrevious') }}</button>
          <button v-if="neighbours.next" :disabled="busy" @click="merge(neighbours.next)">{{ t('trips.detail.actions.mergeNext') }}</button>
          <button :disabled="busy || detail.distance_km <= 0.2" @click="startSplit">{{ t('trips.detail.actions.split') }}</button>
          <button @click="editDetail">{{ t('common.actions.edit') }}</button>
          <button class="danger" @click="deleteDetail">{{ t('common.actions.delete') }}</button>
          <button class="primary" @click="detailId = null">{{ t('common.actions.close') }}</button>
        </div>
      </div>
    </div>

    <RecordDialog v-if="trips.dialog.value" :title="trips.dialog.value.mode === 'create' ? t('trips.dialog.add') : t('trips.dialog.edit')"
      :fields="tripFields" :initial="trips.dialog.value.initial" :mode="trips.dialog.value.mode" :save="trips.save"
      @close="trips.dialog.value = null" />
    <RecordDialog v-if="idle.dialog.value" :title="t('trips.idle.editTitle')" :fields="idleFields"
      :initial="idle.dialog.value.initial" mode="edit" :save="idle.save" @close="idle.dialog.value = null" />
  </div>
</template>

<style scoped>
.facts {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4px 16px;
  margin: 12px 0;
  font-size: 0.9rem;
}
.facts dt {
  color: var(--muted);
}
.facts dd {
  margin: 0;
}
.explain {
  width: 100%;
  font-size: 0.9rem;
}
.explain td {
  padding: 4px 0;
  vertical-align: top;
  white-space: normal; /* the page's tables keep cells on one line */
}
.explain td:first-child {
  width: 90px;
  color: var(--muted);
}
.explain td.num {
  white-space: nowrap;
  padding-left: 16px;
}
.explain tr.total td {
  border-top: 1px solid var(--border);
  font-weight: 600;
}
.split {
  margin-top: 12px;
}
.dialog-actions.wrap {
  flex-wrap: wrap;
}
</style>
