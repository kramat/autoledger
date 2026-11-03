<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, ApiError, type IdleRecord, type Trip } from '../api'
import DataTable, { type Column } from '../components/DataTable.vue'
import RecordDialog from '../components/RecordDialog.vue'
import TripMap from '../components/TripMap.vue'
import { defaultVehicleId, vehicleField, type Field } from '../components/fields'
import { fmtDate, fmtDateTime, fromLocalInput, money, nowLocalInput, num, toLocalInput } from '../format'
import { FACTOR_MODES, label, TRIP_KINDS } from '../labels'
import { activeVehicles, periodRange, state, toast, vehicleName } from '../store'
import { useCrud } from '../useCrud'

const params = () => ({ vehicle_id: state.vehicleId || undefined, ...periodRange() })
const trips = useCrud<Trip>('trips', params, { noun: 'Trip' })
const idle = useCrud<IdleRecord>('idle-records', params, { noun: 'Record' })
const view = ref<'list' | 'map'>('list')
const detailId = ref<string | null>(null)
const detail = computed(() => trips.items.value.find((t) => t.id === detailId.value) ?? null)

function time(value: string): string {
  return new Date(value).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
}

function place(address: string | null, zone: string | null): string {
  return address ?? zone ?? '—'
}

function route(t: Trip): string {
  const from = place(t.start_address, t.start_zone)
  if (t.kind === 'round_trip') return `⟲ ${t.start_zone ?? from}`
  return `${from} → ${place(t.end_address, t.end_zone)}`
}

function fuel(t: Trip): string {
  const litres = t.costing?.fuel_l ?? t.fuel_l
  if (!litres) return '—'
  return `${num(litres, 1)}${t.costing?.fuel_reconciled ? ' ✓' : ''}`
}

function perKm(t: Trip): string {
  return t.costing && t.distance_km >= 1 ? money(t.costing.cost / t.distance_km, 3) : '—'
}

const columns = computed<Column<Trip>[]>(() => [
  { key: 'date', label: 'Date', value: (t) => `${fmtDate(t.start_ts)} ${t.start_ts_estimated ? '~' : ''}${time(t.start_ts)}–${time(t.end_ts)}` },
  ...(!state.vehicleId ? [{ key: 'vehicle', label: 'Vehicle', value: (t: Trip) => vehicleName(t.vehicle_id) }] : []),
  { key: 'route', label: 'From → to', wrap: true, value: route },
  { key: 'km', label: 'km', num: true, value: (t) => num(t.distance_km, 1) },
  { key: 'kwh', label: 'kWh', num: true, value: (t) => (t.costing?.energy_kwh ? num(t.costing.energy_kwh, 2) : '—') },
  { key: 'fuel', label: 'L', num: true, value: fuel },
  { key: 'cost', label: 'Cost', num: true, value: (t) => money(t.costing?.cost) },
  { key: 'per_km', label: 'Per km', num: true, value: perKm },
])

const totals = computed(() => {
  const list = trips.items.value
  const km = list.reduce((s, t) => s + t.distance_km, 0)
  const kwh = list.reduce((s, t) => s + Math.max(t.costing?.energy_kwh ?? 0, 0), 0)
  const litres = list.reduce((s, t) => s + (t.costing?.fuel_l ?? 0), 0)
  const cost = list.reduce((s, t) => s + (t.costing?.cost ?? 0), 0)
  return { km, kwh, litres, cost }
})

const idleTotals = computed(() => ({
  kwh: idle.items.value.reduce((s, r) => s + (r.costing?.energy_kwh ?? 0), 0),
  cost: idle.items.value.reduce((s, r) => s + (r.costing?.cost ?? 0), 0),
}))

const idleColumns = computed<Column<IdleRecord>[]>(() => [
  { key: 'when', label: 'Parked', value: (r) => `${fmtDateTime(r.start_ts)} – ${time(r.end_ts)}` },
  ...(!state.vehicleId ? [{ key: 'vehicle', label: 'Vehicle', value: (r: IdleRecord) => vehicleName(r.vehicle_id) }] : []),
  { key: 'zone', label: 'Where', value: (r) => r.zone ?? '—' },
  { key: 'battery', label: 'Battery', num: true, value: (r) => (r.battery_used_pct ? `−${num(r.battery_used_pct, 1)} %` : '—') },
  { key: 'kwh', label: 'kWh', num: true, value: (r) => (r.costing?.energy_kwh ? num(r.costing.energy_kwh, 2) : '—') },
  { key: 'fuel', label: 'L', num: true, value: (r) => (r.fuel_l ? num(r.fuel_l, 1) : '—') },
  { key: 'cost', label: 'Cost', num: true, value: (r) => money(r.costing?.cost) },
])

const tripFields = computed<Field[]>(() => [
  vehicleField(),
  { key: 'start_ts', label: 'Start', type: 'datetime', required: true, half: true },
  { key: 'end_ts', label: 'End', type: 'datetime', required: true, half: true },
  { key: 'start_address', label: 'From', type: 'text', half: true },
  { key: 'end_address', label: 'To', type: 'text', half: true },
  { key: 'kind', label: 'Kind', type: 'select', options: TRIP_KINDS, half: true },
  { key: 'distance_km', label: 'Distance (km)', type: 'number', min: 0, required: true, half: true },
  { key: 'battery_start_pct', label: 'Battery at start (%)', type: 'number', min: 0, half: true },
  { key: 'battery_end_pct', label: 'Battery at end (%)', type: 'number', min: 0, half: true },
  { key: 'energy_kwh', label: 'Electricity (kWh)', type: 'number', half: true,
    hint: 'Leave empty to derive it from the battery % used.' },
  { key: 'fuel_l', label: 'Fuel (L)', type: 'number', min: 0, half: true },
  { key: 'note', label: 'Note', type: 'textarea' },
])

const idleFields: Field[] = [
  { key: 'zone', label: 'Where', type: 'text' },
  { key: 'battery_used_pct', label: 'Battery used (%)', type: 'number', half: true },
  { key: 'energy_kwh', label: 'Electricity (kWh)', type: 'number', half: true,
    hint: 'Leave empty to derive it from the battery % used.' },
  { key: 'fuel_l', label: 'Fuel (L)', type: 'number', min: 0, half: true },
  { key: 'note', label: 'Note', type: 'textarea' },
]

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

function openDetail(t: Trip): void {
  detailId.value = t.id
  split.value = null
  actionError.value = ''
}

/** Trips of the same vehicle directly before and after, in time order. */
const neighbours = computed(() => {
  const t = detail.value
  if (!t) return { prev: null, next: null }
  const same = trips.items.value.filter((x) => x.vehicle_id === t.vehicle_id).sort((a, b) => a.start_ts.localeCompare(b.start_ts))
  const i = same.findIndex((x) => x.id === t.id)
  return { prev: same[i - 1] ?? null, next: same[i + 1] ?? null }
})

async function restoreAll(created: string[], originals: string[]): Promise<void> {
  for (const id of created) await api.remove('trips', id)
  for (const id of originals) await api.restore('trips', id)
  await trips.load()
}

async function merge(other: Trip): Promise<void> {
  const t = detail.value
  if (!t) return
  busy.value = true
  actionError.value = ''
  try {
    const merged = await api.mergeTrips([t.id, other.id])
    await trips.load()
    detailId.value = merged.id
    toast('Trips merged', 'Undo', () => restoreAll([merged.id], [t.id, other.id]))
  } catch (err) {
    actionError.value = (err as Error).message
  } finally {
    busy.value = false
  }
}

function startSplit(): void {
  const t = detail.value
  if (!t) return
  const middle = new Date((new Date(t.start_ts).getTime() + new Date(t.end_ts).getTime()) / 2).toISOString()
  split.value = { km: String(Math.round((t.distance_km / 2) * 10) / 10), at: toLocalInput(middle), address: '' }
}

async function doSplit(): Promise<void> {
  const t = detail.value
  if (!t || !split.value) return
  busy.value = true
  actionError.value = ''
  try {
    const parts = await api.splitTrip(t.id, {
      at_km: Number(split.value.km),
      at_ts: fromLocalInput(split.value.at),
      address: split.value.address.trim() || null,
    })
    await trips.load()
    detailId.value = parts[0].id
    split.value = null
    toast('Trip split', 'Undo', () => restoreAll(parts.map((p) => p.id), [t.id]))
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
  const t = detail.value
  detailId.value = null
  await trips.remove(t)
}

const showIdle = computed(() => idle.items.value.length > 0)
const noCollector = computed(() =>
  activeVehicles.value.filter((v) => !state.vehicleId || v.id === state.vehicleId).every((v) => v.tracking !== 'collector'),
)
</script>

<template>
  <div class="stack">
    <div class="page-head">
      <h2>Trips</h2>
      <div class="actions">
        <div class="segmented" role="group" aria-label="Display">
          <button :class="{ on: view === 'list' }" :aria-pressed="view === 'list'" @click="view = 'list'">List</button>
          <button :class="{ on: view === 'map' }" :aria-pressed="view === 'map'" @click="view = 'map'">Map</button>
        </div>
        <a :href="api.exportUrl('trips', params())" download><button>Export CSV</button></a>
        <button class="primary" :disabled="!activeVehicles.length" @click="add">Add trip</button>
      </div>
    </div>
    <p v-if="trips.error.value" class="notice error">{{ trips.error.value }}</p>

    <div v-if="trips.items.value.length" class="stats card">
      <div class="stat"><div class="label">Trips</div><div class="value">{{ trips.items.value.length }}</div>
        <div class="sub">{{ num(totals.km, 1) }} km</div></div>
      <div class="stat"><div class="label">Electricity</div><div class="value">{{ num(totals.kwh, 1) }} kWh</div>
        <div class="sub">{{ totals.km >= 1 ? `${num((totals.kwh / totals.km) * 100, 1)} kWh/100 km` : '—' }}</div></div>
      <div class="stat"><div class="label">Fuel</div><div class="value">{{ num(totals.litres, 1) }} L</div>
        <div class="sub">{{ totals.km >= 1 ? `${num((totals.litres / totals.km) * 100, 1)} L/100 km` : '—' }}</div></div>
      <div class="stat"><div class="label">Cost</div><div class="value">{{ money(totals.cost) }}</div>
        <div class="sub">{{ totals.km >= 1 ? `${money(totals.cost / totals.km, 3)} / km` : '—' }}</div></div>
    </div>

    <TripMap v-if="view === 'map'" :trips="trips.items.value" :selected="detailId" @select="openDetail" />
    <DataTable v-else :columns="columns" :rows="trips.items.value" :loading="trips.loading.value"
      :empty="noCollector
        ? 'Trips are recorded automatically for cars set up in the AutoLedger Collector. A manual vehicle\'s distance comes from its odometer readings.'
        : 'No trips in this period.'"
      :extra="{ label: () => 'Details', run: openDetail }" @edit="trips.openEdit" @delete="trips.remove" />
    <p class="small muted">
      ~ before a time: the car reported only after the trip, so the start is when it was last seen parked.
      Fuel is smoothed for gauge noise, so it can still shift a little with the next reports; ✓ fuel: corrected
      with the litres refuelled between two full tanks.
    </p>

    <section v-if="showIdle" class="card">
      <h2>Climate &amp; standby</h2>
      <p class="small muted">
        Energy used while parked (pre-heating, standby). It is part of the energy cost, but not of the consumption per km.
      </p>
      <DataTable :columns="idleColumns" :rows="idle.items.value" empty="" @edit="idle.openEdit" @delete="idle.remove">
        <template #foot>
          <tr>
            <td :colspan="state.vehicleId ? 3 : 4">{{ idle.items.value.length }} records</td>
            <td class="num">{{ num(idleTotals.kwh, 2) }}</td>
            <td></td>
            <td class="num">{{ money(idleTotals.cost) }}</td>
            <td></td>
          </tr>
        </template>
      </DataTable>
    </section>

    <div v-if="detail" class="overlay" @click.self="detailId = null">
      <div class="dialog" role="dialog" aria-modal="true" aria-label="Trip details">
        <h2>{{ route(detail) }}</h2>
        <p class="small muted" style="margin-top: -6px">
          {{ fmtDateTime(detail.start_ts) }} – {{ time(detail.end_ts) }}
          <template v-if="detail.start_ts_estimated"> · start estimated</template>
          · {{ num(detail.distance_km, 1) }} km
          ({{ detail.distance_source === 'trip_meter' ? 'trip meter' : detail.distance_source }})
        </p>

        <dl class="facts">
          <template v-if="detail.odometer_start != null">
            <dt>Odometer</dt><dd>{{ num(detail.odometer_start) }} → {{ num(detail.odometer_end) }} km</dd>
          </template>
          <template v-if="detail.battery_used_pct != null">
            <dt>Battery</dt>
            <dd>{{ num(detail.battery_start_pct, 1) }} → {{ num(detail.battery_end_pct, 1) }} % (used {{ num(detail.battery_used_pct, 1) }} %)</dd>
          </template>
          <template v-if="detail.charged_kwh">
            <dt>Charged in between</dt><dd>{{ num(detail.charged_kwh, 2) }} kWh</dd>
          </template>
          <template v-if="detail.fuel_start_l != null">
            <dt>Tank</dt><dd>{{ num(detail.fuel_start_l, 1) }} → {{ num(detail.fuel_end_l, 1) }} L</dd>
          </template>
        </dl>

        <template v-if="detail.costing">
          <h3 class="small">How the cost was calculated</h3>
          <table class="explain">
            <tbody>
              <tr>
                <td>Electricity</td>
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
                <td>Fuel</td>
                <td>
                  {{ num(detail.costing.fuel_l, 2) }} L
                  <template v-if="detail.costing.fuel_reconciled">(gauge {{ num(detail.costing.fuel_l_measured, 2) }} L, corrected at the full tank)</template>
                  <template v-else-if="Math.abs(detail.costing.fuel_l_measured - detail.costing.fuel_l) >= 0.005">(gauge
                    {{ num(detail.costing.fuel_l_measured, 2) }} L, smoothed for gauge noise; provisional until the next full tank)</template>
                  <template v-else-if="detail.costing.fuel_l">(provisional until the next full tank)</template>
                  × {{ money(detail.costing.l_price, 3) }}
                </td>
                <td class="num">{{ money(detail.costing.fuel_cost) }}</td>
              </tr>
              <tr class="total"><td>Trip</td><td>{{ perKm(detail) }} / km</td><td class="num">{{ money(detail.costing.cost) }}</td></tr>
            </tbody>
          </table>
          <p class="small muted">
            Prices are the average of what is in the battery and in the tank: your charges and refuels, mixed in proportion.
          </p>
          <ul v-if="detail.costing.notes.length" class="small">
            <li v-for="n in detail.costing.notes" :key="n">{{ n }}</li>
          </ul>
        </template>
        <p v-if="detail.note" class="small">{{ detail.note }}</p>

        <form v-if="split" class="form-grid split" @submit.prevent="doSplit">
          <label class="field half"><span>Stop after (km)</span>
            <input v-model="split.km" type="number" step="0.1" min="0.1" required /></label>
          <label class="field half"><span>Stop time</span>
            <input v-model="split.at" type="datetime-local" required /></label>
          <label class="field"><span>Stop place</span>
            <input v-model="split.address" type="text" placeholder="e.g. Albert Heijn" /></label>
          <div class="dialog-actions" style="grid-column: 1 / -1">
            <button type="button" @click="split = null">Cancel</button>
            <button type="submit" class="primary" :disabled="busy">Split trip</button>
          </div>
        </form>
        <p v-if="actionError" class="notice error">{{ actionError }}</p>

        <div v-if="!split" class="dialog-actions wrap">
          <button v-if="neighbours.prev" :disabled="busy" @click="merge(neighbours.prev)">Merge with previous</button>
          <button v-if="neighbours.next" :disabled="busy" @click="merge(neighbours.next)">Merge with next</button>
          <button :disabled="busy || detail.distance_km <= 0.2" @click="startSplit">Split…</button>
          <button @click="editDetail">Edit</button>
          <button class="danger" @click="deleteDetail">Delete</button>
          <button class="primary" @click="detailId = null">Close</button>
        </div>
      </div>
    </div>

    <RecordDialog v-if="trips.dialog.value" :title="trips.dialog.value.mode === 'create' ? 'Add trip' : 'Edit trip'"
      :fields="tripFields" :initial="trips.dialog.value.initial" :mode="trips.dialog.value.mode" :save="trips.save"
      @close="trips.dialog.value = null" />
    <RecordDialog v-if="idle.dialog.value" title="Edit climate & standby" :fields="idleFields"
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
