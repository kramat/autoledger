<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api, type MaintenanceRecord, type MaintenanceSchedule, type ScheduleDue, type VehicleDue } from '../api'
import DataTable, { type Column } from '../components/DataTable.vue'
import RecordDialog from '../components/RecordDialog.vue'
import { defaultVehicleId, vehicleField, type Field } from '../components/fields'
import { fmtDate, isoDate, km, money, num } from '../format'
import { DUE_STATUSES, label, MAINTENANCE_CATEGORIES } from '../labels'
import { activeVehicles, state, vehicleName } from '../store'
import { useCrud } from '../useCrud'

const params = () => ({ vehicle_id: state.vehicleId || undefined })
const due = ref<VehicleDue[]>([])

async function loadDue(): Promise<void> {
  due.value = (await api.maintenanceDue(params())).vehicles
}

const crud = useCrud<MaintenanceRecord>('maintenance', params, {
  noun: 'Maintenance entry',
  // A logged entry can move a schedule forward.
  afterChange: async () => {
    await Promise.all([loadDue(), schedules.load()])
  },
})
const schedules = useCrud<MaintenanceSchedule>('maintenance-schedules', params, {
  noun: 'Schedule',
  afterChange: loadDue,
})
watch(params, () => loadDue().catch(() => undefined), { immediate: true, deep: true })

const scheduleName = (id: string | null) => schedules.items.value.find((s) => s.id === id)?.name ?? ''

const columns = computed<Column<MaintenanceRecord>[]>(() => [
  { key: 'date', label: 'Date', value: (r) => fmtDate(r.date) },
  ...(!state.vehicleId
    ? [{ key: 'vehicle', label: 'Vehicle', value: (r: MaintenanceRecord) => vehicleName(r.vehicle_id) }]
    : []),
  { key: 'category', label: 'Category', value: (r) => label(MAINTENANCE_CATEGORIES, r.category) },
  { key: 'description', label: 'Description', wrap: true, value: (r) => r.description },
  { key: 'schedule', label: 'Schedule', wrap: true, value: (r) => scheduleName(r.schedule_id) },
  { key: 'garage', label: 'Garage', wrap: true, value: (r) => r.garage ?? '' },
  { key: 'odometer', label: 'Odometer', num: true, value: (r) => km(r.odometer_km) },
  { key: 'cost', label: 'Cost', num: true, value: (r) => money(r.cost) },
])

const scheduleOptions = computed(() => [
  { value: null, label: 'By category (automatic)' },
  ...schedules.items.value
    .filter((s) => s.active)
    .map((s) => ({ value: s.id, label: activeVehicles.value.length > 1 ? `${vehicleName(s.vehicle_id)} · ${s.name}` : s.name })),
])

const fields = computed<Field[]>(() => [
  vehicleField(),
  { key: 'date', label: 'Date', type: 'date', required: true, half: true },
  { key: 'category', label: 'Category', type: 'select', options: MAINTENANCE_CATEGORIES, required: true, half: true },
  { key: 'description', label: 'Description', type: 'text', required: true, placeholder: 'e.g. Yearly service + oil' },
  { key: 'odometer_km', label: 'Odometer (km)', type: 'number', min: 0, half: true },
  { key: 'cost', label: 'Cost', type: 'number', min: 0, half: true },
  {
    key: 'schedule_id', label: 'Counts for schedule', type: 'select', options: scheduleOptions.value,
    hint: 'Automatic: it counts for every schedule with the same category.',
  },
  { key: 'garage', label: 'Garage', type: 'text' },
  { key: 'note', label: 'Note', type: 'textarea' },
])

const scheduleFields = computed<Field[]>(() => [
  vehicleField(),
  { key: 'name', label: 'Name', type: 'text', required: true, placeholder: 'e.g. Service, APK, Brake fluid' },
  {
    key: 'category', label: 'Category', type: 'select',
    options: [{ value: null, label: 'None (only linked entries count)' }, ...MAINTENANCE_CATEGORIES],
    hint: 'Maintenance entries of this category move the schedule forward.',
  },
  { key: 'interval_months', label: 'Every … months', type: 'number', min: 1, step: '1', half: true },
  { key: 'interval_km', label: 'or every … km', type: 'number', min: 0, half: true },
  { key: 'last_done_date', label: 'Last done on', type: 'date', half: true },
  { key: 'last_done_km', label: 'at odometer (km)', type: 'number', min: 0, half: true },
  { key: 'remind_before_days', label: 'Remind … days before', type: 'number', min: 0, step: '1', half: true },
  { key: 'remind_before_km', label: 'or … km before', type: 'number', min: 0, half: true },
  { key: 'active', label: 'Active', type: 'checkbox' },
  { key: 'note', label: 'Note', type: 'textarea' },
])

const total = computed(() => crud.items.value.reduce((sum, r) => sum + r.cost, 0))

function add(initial: Record<string, unknown> = {}): void {
  crud.openCreate({ vehicle_id: defaultVehicleId(), date: isoDate(new Date()), category: 'service', cost: 0, ...initial })
}

function addSchedule(): void {
  schedules.openCreate({
    vehicle_id: defaultVehicleId(), category: 'service', interval_months: 12, remind_before_days: 30,
    remind_before_km: 1000, active: true,
  })
}

function logDone(vehicle: VehicleDue, item: VehicleDue['items'][number]): void {
  // A connected car's odometer is current; a manual car's last value can be weeks old.
  const collector = state.vehicles.find((v) => v.id === vehicle.vehicle_id)?.tracking === 'collector'
  add({
    vehicle_id: vehicle.vehicle_id, category: item.category ?? 'other', description: item.name,
    schedule_id: item.schedule_id, odometer_km: collector ? vehicle.odometer_km : null,
  })
}

function every(item: { interval_months: number | null; interval_km: number | null }): string {
  const parts = []
  if (item.interval_months) parts.push(item.interval_months === 12 ? 'every year' : `every ${item.interval_months} months`)
  if (item.interval_km) parts.push(`every ${num(item.interval_km)} km`)
  return parts.join(' or ')
}

function when(item: ScheduleDue): string {
  if (item.status === 'unknown') return 'Set when it was last done'
  const parts = []
  if (item.estimated_date) {
    const days = item.days_left ?? 0
    const relative = days === 0 ? 'today' : days > 0 ? `in ${days} days` : `${-days} days ago`
    parts.push(`${fmtDate(item.estimated_date)} (${relative}${item.reason === 'km' ? ', estimated from km' : ''})`)
  }
  if (item.km_left != null) {
    parts.push(item.km_left >= 0 ? `${km(item.km_left)} left` : `${km(-item.km_left)} over`)
  }
  return parts.join(' · ')
}

function editSchedule(id: string): void {
  const schedule = schedules.items.value.find((s) => s.id === id)
  if (schedule) schedules.openEdit(schedule)
}

function removeSchedule(id: string): void {
  const schedule = schedules.items.value.find((s) => s.id === id)
  if (schedule) schedules.remove(schedule)
}

const inactive = computed(() => schedules.items.value.filter((s) => !s.active))
</script>

<template>
  <div class="stack">
    <section class="card">
      <div class="page-head">
        <h2>Schedules</h2>
        <div class="actions">
          <button :disabled="!activeVehicles.length" @click="addSchedule">Add schedule</button>
        </div>
      </div>
      <p v-if="schedules.error.value" class="notice error">{{ schedules.error.value }}</p>
      <template v-for="v in due" :key="v.vehicle_id">
        <h3 v-if="!state.vehicleId && due.length > 1" class="small muted" style="margin: 12px 0 4px">{{ v.vehicle_name }}</h3>
        <div v-if="v.items.length" class="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Schedule</th><th scope="col">Status</th><th scope="col">Next due</th>
                <th scope="col">Last done</th><th><span class="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in v.items" :key="item.schedule_id">
                <td class="wrap"><b>{{ item.name }}</b><br /><span class="small muted">{{ every(item) }}</span></td>
                <td><span class="badge" :class="item.status">{{ DUE_STATUSES[item.status] }}</span></td>
                <td class="wrap">{{ when(item) }}</td>
                <td class="wrap">
                  {{ item.last_done_date ? fmtDate(item.last_done_date) : '—' }}<template v-if="item.last_done_km != null">
                    · {{ km(item.last_done_km) }}</template>
                </td>
                <td class="row-actions">
                  <button class="link" @click="logDone(v, item)">Log as done</button>
                  <button class="link" @click="editSchedule(item.schedule_id)">Edit</button>
                  <button class="link danger" @click="removeSchedule(item.schedule_id)">Delete</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="v.car_service" class="small muted" style="margin: 8px 0 0">
          The car itself reports: service
          <template v-if="v.car_service.due_date">around {{ fmtDate(v.car_service.due_date) }}
            ({{ num(v.car_service.days_to_service) }} days)</template>
          <template v-if="v.car_service.due_date && v.car_service.distance_to_service != null"> or </template>
          <template v-if="v.car_service.distance_to_service != null">in {{ km(v.car_service.distance_to_service) }}<template
              v-if="v.car_service.due_km != null"> (at {{ km(v.car_service.due_km) }})</template></template>,
          as of {{ fmtDate(v.car_service.reported_at) }}.
        </p>
        <p v-if="v.items.length && v.km_per_day != null" class="small muted" style="margin: 4px 0 0">
          Dates for km intervals are estimated from {{ num(v.km_per_day) }} km per day (last 90 days).
        </p>
      </template>
      <div v-if="!due.some((v) => v.items.length)" class="empty">
        No schedules yet. Add one for the yearly service or the APK, and AutoLedger tells you when it is due, here and
        in Home Assistant.
      </div>
      <p v-if="inactive.length" class="small muted" style="margin: 8px 0 0">
        Paused: <template v-for="(s, i) in inactive" :key="s.id"><button class="link" @click="schedules.openEdit(s)">{{
          s.name }}</button><template v-if="i < inactive.length - 1">, </template></template>
      </p>
    </section>

    <section>
      <div class="page-head">
        <h2>Maintenance log</h2>
        <div class="actions">
          <a :href="api.exportUrl('maintenance', params())" download><button>Export CSV</button></a>
          <button class="primary" :disabled="!activeVehicles.length" @click="add()">Add maintenance</button>
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
    </section>

    <RecordDialog v-if="crud.dialog.value"
      :title="crud.dialog.value.mode === 'create' ? 'Add maintenance' : 'Edit maintenance'" :fields="fields"
      :initial="crud.dialog.value.initial" :mode="crud.dialog.value.mode" :save="crud.save"
      @close="crud.dialog.value = null" />
    <RecordDialog v-if="schedules.dialog.value"
      :title="schedules.dialog.value.mode === 'create' ? 'Add schedule' : 'Edit schedule'" :fields="scheduleFields"
      :initial="schedules.dialog.value.initial" :mode="schedules.dialog.value.mode" :save="schedules.save"
      @close="schedules.dialog.value = null" />
  </div>
</template>
